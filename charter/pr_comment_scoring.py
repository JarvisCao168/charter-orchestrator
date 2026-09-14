"""Real GitHub PR comment scoring (v2.5).

Lifts `charter/pr_community.py` (in-process community scoring) to a
**real GitHub PR comment / reaction** reader: fetches a PR's review
comments + issue/reaction counts via the GitHub REST API, and folds them
into a weighted score (the same helpful/adopted/reported model
`pr_community.community_score` uses, but sourced from *live* PR signals
instead of an in-process registry).

    - `fetch_pr_signals(pr_number, repo, token)` - GET /repos/{repo}/pulls/
      {number} + /issues/{number}/comments + /issues/{number}/reactions.
      Returns a `PRSignals` (n_reviews, n_positive, n_negative, n_comment,
      n_approved, n_changes_requested, labels).
    - `score_from_pr(signals, weights)` - fold signals into the same
      0..1 weighted score as `pr_community.community_score`
      (usefulness / adoption / health blend).
    - `auto_merge_gate(score, threshold)` - boolean: should this template PR
      auto-merge based on its community score?

Stdlib-only (urllib). Offline-safe: `fetch_pr_signals` returns a
`PRSignals` with a `live=False` flag + an empty body when no token is
configured or the network is unreachable, so callers can still run
`score_from_pr` on the empty signals (score = 0.0) and the auto-merge gate
degrades to "do not auto-merge" (conservative default).
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

__all__ = [
    "PRSignals", "fetch_pr_signals", "score_from_pr", "auto_merge_gate",
]

_API = "https://api.github.com"


@dataclass
class PRSignals:
    """Live GitHub PR signals folded into a community score.

    `live=True` means the numbers came from a real GitHub API call;
    `live=False` means they are the empty / offline-safe defaults.
    """
    pr_number: int
    n_reviews: int = 0
    n_approved: int = 0
    n_changes_requested: int = 0
    n_comments: int = 0
    n_reactions_positive: int = 0     # +1 / heart / laugh / hooray
    n_reactions_negative: int = 0     # -1 / confused / sad
    labels: Dict[str, int] = field(default_factory=dict)
    live: bool = False
    errors: list = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def adopted(self) -> int:
        """'adopted' signal = approved reviews (a proxy for adoption)."""
        return self.n_approved

    def reported(self) -> int:
        """'reported' signal = changes-requested + negative reactions."""
        return self.n_changes_requested + self.n_reactions_negative


def _gh_get(url: str, token: str, timeout: int = 20) -> Dict[str, Any]:
    headers = {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "charter-orchestrator",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except Exception as exc:
        raise


def fetch_pr_signals(pr_number: int,
                     repo: str,
                     token: Optional[str] = None,
                     timeout: int = 20) -> PRSignals:
    """tool: fetch_pr_signals - read a live PR's review + reaction signals.

    No token / unreachable network -> returns a PRSignals(live=False) with
    empty numbers + the error recorded, never raises.
    """
    token = token or os.environ.get("GITHUB_TOKEN") or \
        os.environ.get("GH_TOKEN") or ""
    sig = PRSignals(pr_number=pr_number, live=bool(token))

    if not token or not repo:
        sig.errors.append(
            "no GITHUB_TOKEN or repo configured; returning empty signals")
        return sig

    try:
        # 1. PR itself (labels + state)
        pr = _gh_get(f"{_API}/repos/{repo}/pulls/{pr_number}", token,
                     timeout)
        sig.labels = {l["name"]: 1 for l in pr.get("labels", [])}
        sig.raw["pr"] = {"state": pr.get("state"),
                          "labels": list(sig.labels)}

        # 2. review comments (GET /repos/{repo}/pulls/{n}/comments)
        review_comments = _gh_get(
            f"{_API}/repos/{repo}/pulls/{pr_number}/comments",
            token, timeout).get("items",
            _gh_get(f"{_API}/repos/{repo}/pulls/{pr_number}/comments",
                    token, timeout))
        # the response above is a list directly (not wrapped in items)
        if isinstance(review_comments, list):
            pass
        else:
            review_comments = []

        # 3. review state (GET /repos/{repo}/pulls/{n}/reviews)
        reviews = _gh_get(
            f"{_API}/repos/{repo}/pulls/{pr_number}/reviews", token,
            timeout)
        reviews = reviews if isinstance(reviews, list) else []
        for r in reviews:
            state = r.get("state", "").lower()
            sig.n_reviews += 1
            if state == "approved":
                sig.n_approved += 1
            elif state == "changes_requested":
                sig.n_changes_requested += 1

        # 4. issue comments
        comments = _gh_get(
            f"{_API}/repos/{repo}/issues/{pr_number}/comments", token,
            timeout)
        sig.n_comments = len(comments) if isinstance(comments, list) else 0

        # 5. reactions (GET /repos/{repo}/issues/{n}/reactions, paginated)
        reactions = _gh_get(
            f"{_API}/repos/{repo}/issues/{pr_number}/reactions", token,
            timeout)
        reactions = reactions if isinstance(reactions, list) else []
        pos = {"+1", "heart", "laugh", "hooray"}
        neg = {"-1", "confused", "sad"}
        for r in reactions:
            content = (r.get("content") or "").lower()
            if content in pos:
                sig.n_reactions_positive += 1
            elif content in neg:
                sig.n_reactions_negative += 1

        return sig
    except Exception as exc:
        sig.errors.append(str(exc)[:300])
        sig.live = False
        return sig


def score_from_pr(signals: PRSignals,
                  w_helpful: float = 0.4,
                  w_adopted: float = 0.35,
                  w_health: float = 0.25) -> Dict[str, Any]:
    """Fold PR signals into a 0..1 community score (same blend as
    pr_community.community_score, but sourced from live PR data).

    usefulness  = positive_reactions / (positive + negative + comments)
    adoption    = approved_reviews  / (reviews + 1)
    health      = 1 - changes_requested / (reviews + 1)
    """
    pos = signals.n_reactions_positive
    neg = signals.n_reactions_negative
    comments = signals.n_comments
    total_reacts = pos + neg + max(1, comments)
    usefulness = pos / total_reacts

    reviews = max(1, signals.n_reviews)
    adoption = signals.adopted() / reviews
    health = max(0.0, 1.0 - signals.reported() / reviews)

    score = round(w_helpful * usefulness + w_adopted * adoption +
                  w_health * health, 4)
    return {
        "pr_number": signals.pr_number,
        "live": signals.live,
        "score": score,
        "usefulness": round(usefulness, 4),
        "adoption": round(adoption, 4),
        "health": round(health, 4),
        "signals": signals,
        "errors": signals.errors,
    }


def auto_merge_gate(score: Dict[str, Any],
                    threshold: float = 0.6,
                    require_live: bool = True,
                    min_reviews: int = 1) -> Dict[str, Any]:
    """tool: auto_merge_gate - should this PR auto-merge?

    Conservative default: auto-merge only when the score is above
    `threshold`, the data is live (or `require_live=False`), and there
    are at least `min_reviews` reviews. Returns {auto_merge: bool,
    reasons: [...]}.
    """
    reasons: list = []
    ok = score["score"] >= threshold
    if not ok:
        reasons.append(
            f"score {score['score']} < threshold {threshold}")
    if require_live and not score.get("live"):
        ok = False
        reasons.append("signals not live (offline / no token)")
    n_reviews = score.get("signals", None)
    if n_reviews is not None and \
            getattr(n_reviews, "n_reviews", 0) < min_reviews:
        ok = False
        reasons.append(
            f"only {getattr(n_reviews, 'n_reviews', 0)} review(s) "
            f"< {min_reviews}")
    if not reasons:
        reasons.append("auto-merge eligible")
    return {"auto_merge": ok, "score": score["score"],
            "threshold": threshold, "reasons": reasons}
