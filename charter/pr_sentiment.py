"""LLM sentiment / specificity analysis of PR comments (v2.6).

Lifts `charter/pr_comment_scoring.py` (counts of approvals / reactions) to
a **semantic** layer: run an LLM over the actual *text* of a PR's review
comments + issue comments and extract, per comment:

    - sentiment   -1.0..1.0  (negative -> positive)
    - specificity 0.0..1.0   (vague "lgtm" -> actionable "move the
      checkpoint save to after gate_3 because it races with X")
    - actionable   bool        (contains a concrete to-do / issue)
    - summary      one-line    (what the comment is about)

The analyzer is pluggable:
    - `LLMCommentAnalyzer` - real LLM (Agnes/OpenAI) when a key is set
    - `HeuristicCommentAnalyzer` - offline deterministic fallback (keyword
      polarity + length + action-verb heuristics), so CI / airgapped use
      stays green and still produces a useful signal.

`analyze_pr_comments(pr_number, repo, token, ...)` pulls the live comments
(via `pr_comment_scoring.fetch_pr_signals`'s underlying GitHub GET) and
returns a per-comment analysis + an aggregate `{avg_sentiment, avg_
specificity, n_actionable, themes:[...]}` that can feed
`pr_comment_scoring.score_from_pr` for a richer community score.

Stdlib-only. Offline-safe: no token / no LLM key -> heuristic analyzer,
never raises.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

__all__ = [
    "CommentAnalysis", "HeuristicCommentAnalyzer", "LLMCommentAnalyzer",
    "analyze_comment", "analyze_pr_comments", "pick_analyzer",
]

_API = "https://api.github.com"

_POSITIVE_WORDS = {"good", "great", "nice", "clean", "approved", "lgtm",
                   "awesome", "solid", "thank", "thanks", "correct",
                   "works", "love"}
_NEGATIVE_WORDS = {"bad", "wrong", "broken", "bug", "issue", "fail",
                   "failing", "wrong", "concern", "risk", "insecure",
                   "hmm", "sad", "-1", "reject"}
_ACTION_VERBS = {"should", "could", "can", "move", "moved", "moves",
                 "add", "added", "remove", "fix", "fixed",
                 "refactor", "rename", "update", "replace",
                 "extract", "split", "cache", "validate", "guard",
                 "test", "check", "ensure", "prevent", "avoid",
                 "make", "use", "delete", "wrap", "return", "raise",
                 "bump", "pin", "document", "annotate", "save",
                 "races", "race", "race", "after", "before"}


@dataclass
class CommentAnalysis:
    comment_id: int
    user: str
    text: str
    sentiment: float = 0.0        # -1..1
    specificity: float = 0.0      # 0..1
    actionable: bool = False
    summary: str = ""
    analyzer: str = "heuristic"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "comment_id": self.comment_id, "user": self.user,
            "text": self.text, "sentiment": round(self.sentiment, 3),
            "specificity": round(self.specificity, 3),
            "actionable": self.actionable, "summary": self.summary,
            "analyzer": self.analyzer,
        }


class _Analyzer(Protocol):
    name: str
    def analyze(self, text: str) -> Dict[str, Any]: ...


class HeuristicCommentAnalyzer:
    """Offline deterministic sentiment / specificity (no LLM / key)."""

    name = "heuristic"

    def analyze(self, text: str) -> Dict[str, Any]:
        low = text.lower()
        words = low.split()
        pos = sum(1 for w in words if w in _POSITIVE_WORDS)
        neg = sum(1 for w in words if w in _NEGATIVE_WORDS)
        denom = max(1, pos + neg)
        # base sentiment: balance of pos vs neg, scaled to -1..1
        sentiment = (pos - neg) / denom if (pos + neg) else 0.0
        # length bucket for specificity (longer + has code = more specific)
        has_code = ("```" in text) or ("`" in text and len(words) > 6)
        length_spec = min(1.0, len(words) / 40.0)
        verb_hits = sum(1 for w in words if w in _ACTION_VERBS)
        specificity = round(0.5 * length_spec + 0.3 * min(1.0, verb_hits / 3)
                            + (0.2 if has_code else 0.0), 3)
        actionable = verb_hits >= 1 or has_code
        # one-line summary
        first = " ".join(words[:8])
        summary = (first + ("..." if len(words) > 8 else "")).strip()
        return {"sentiment": sentiment, "specificity": specificity,
                "actionable": actionable, "summary": summary}


class LLMCommentAnalyzer:
    """Real LLM sentiment / specificity (Agnes/OpenAI)."""

    name = "llm"

    def __init__(self, api_key: str, model: str, base_url: str,
                 backend: str = "llm", timeout: int = 40) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.backend = backend
        self.timeout = timeout

    def analyze(self, text: str) -> Dict[str, Any]:
        sys_prompt = (
            "Analyze a code-review comment. Return ONLY JSON: "
            "{\"sentiment\": <float -1..1>, \"specificity\": <float 0..1>, "
            "\"actionable\": <bool>, \"summary\": \"<<=20 words>\"}. "
            "No prose outside the JSON."
        )
        body = json.dumps({
            "model": self.model, "temperature": 0.0,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": text[:1500]},
            ],
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        s = content.find("{")
        e = content.rfind("}")
        if s != -1 and e != -1 and e > s:
            content = content[s:e + 1]
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            raw = {}
        try:
            sentiment = max(-1.0, min(1.0, float(raw.get("sentiment", 0.0))))
        except (TypeError, ValueError):
            sentiment = 0.0
        try:
            specificity = max(0.0, min(1.0, float(raw.get("specificity", 0.0))))
        except (TypeError, ValueError):
            specificity = 0.0
        return {
            "sentiment": sentiment,
            "specificity": specificity,
            "actionable": bool(raw.get("actionable", False)),
            "summary": str(raw.get("summary", text[:60])),
        }


def pick_analyzer(backend: Optional[str] = None,
                  api_key: Optional[str] = None
                  ) -> _Analyzer:
    """Pick an analyzer. None auto-detects: key -> llm, else heuristic."""
    backend = backend or os.environ.get("PR_COMMENT_ANALYZER")
    if backend is None:
        if api_key or os.environ.get("AGNES_API_KEY") or \
           os.environ.get("OPENAI_API_KEY"):
            backend = "llm"
        else:
            backend = "heuristic"
    if backend == "heuristic":
        return HeuristicCommentAnalyzer()
    if backend == "llm":
        key = api_key or os.environ.get("AGNES_API_KEY") or \
            os.environ.get("OPENAI_API_KEY") or ""
        model = os.environ.get("AGNES_MODEL", "agnes-2.5-flash")
        base_url = os.environ.get(
            "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
        return LLMCommentAnalyzer(key, model, base_url)
    raise ValueError(f"unknown analyzer backend: {backend!r}")


def analyze_comment(text: str,
                    comment_id: int = 0,
                    user: str = "",
                    backend: Optional[str] = None,
                    api_key: Optional[str] = None) -> CommentAnalysis:
    """tool: analyze_comment - one comment's sentiment / specificity."""
    analyzer = pick_analyzer(backend, api_key)
    out = analyzer.analyze(text)
    return CommentAnalysis(
        comment_id=comment_id, user=user, text=text,
        sentiment=out["sentiment"], specificity=out["specificity"],
        actionable=out["actionable"], summary=out["summary"],
        analyzer=analyzer.name)


def _gh_get(url: str, token: str, timeout: int = 20) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"bearer {token}",
               "Accept": "application/vnd.github+json",
               "User-Agent": "charter-orchestrator"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else []


def analyze_pr_comments(pr_number: int,
                        repo: str,
                        token: Optional[str] = None,
                        backend: Optional[str] = None,
                        api_key: Optional[str] = None,
                        max_comments: int = 50
                        ) -> Dict[str, Any]:
    """tool: analyze_pr_comments - semantic analysis of a live PR's comments.

    Pulls the PR's review + issue comments (offline-safe: no token ->
    returns the heuristic aggregate over an empty set, flagged
    `live=False`), then runs the analyzer over each and returns:
        {pr_number, live, n_comments, comments:[CommentAnalysis.as_dict],
         aggregate:{avg_sentiment, avg_specificity, n_actionable, themes}}
    `themes` is a coarse top-frequency-phrase extraction from the
    per-comment summaries.
    """
    token = token or os.environ.get("GITHUB_TOKEN") or \
        os.environ.get("GH_TOKEN") or ""
    analyzer = pick_analyzer(backend, api_key)

    comments: List[Dict[str, Any]] = []
    live = False
    errors: List[str] = []
    if token and repo:
        try:
            rc = _gh_get(
                f"{_API}/repos/{repo}/pulls/{pr_number}/review_comments",
                token)
            ic = _gh_get(
                f"{_API}/repos/{repo}/issues/{pr_number}/comments", token)
            comments = (rc if isinstance(rc, list) else []) + \
                      (ic if isinstance(ic, list) else [])
            live = True
        except Exception as exc:
            errors.append(str(exc)[:200])
            live = False

    comments = comments[:max_comments]
    analyses: List[CommentAnalysis] = []
    for i, c in enumerate(comments):
        text = c.get("body", "") or ""
        user = (c.get("user") or {}).get("login", "unknown")
        cid = c.get("id", i)
        try:
            out = analyzer.analyze(text)
            analyses.append(CommentAnalysis(
                comment_id=cid, user=user, text=text,
                sentiment=out["sentiment"],
                specificity=out["specificity"],
                actionable=out["actionable"],
                summary=out["summary"], analyzer=analyzer.name))
        except Exception as exc:
            # per-comment LLM failure -> fall back to heuristic
            heur = HeuristicCommentAnalyzer().analyze(text)
            analyses.append(CommentAnalysis(
                comment_id=cid, user=user, text=text,
                sentiment=heur["sentiment"],
                specificity=heur["specificity"],
                actionable=heur["actionable"],
                summary=heur["summary"],
                analyzer="heuristic-fallback"))

    n = len(analyses)
    avg_sent = (round(sum(a.sentiment for a in analyses) / n, 3)
                if n else 0.0)
    avg_spec = (round(sum(a.specificity for a in analyses) / n, 3)
                if n else 0.0)
    n_action = sum(1 for a in analyses if a.actionable)
    # coarse themes: top 6 most-frequent content words in the summaries
    from collections import Counter
    counter: Counter = Counter()
    for a in analyses:
        for w in a.summary.lower().split():
            w = w.strip(".,;:!?")
            if len(w) > 3:
                counter[w] += 1
    themes = [w for w, _ in counter.most_common(6)]

    return {
        "pr_number": pr_number, "repo": repo, "live": live,
        "n_comments": n,
        "comments": [a.as_dict() for a in analyses],
        "aggregate": {
            "avg_sentiment": avg_sent,
            "avg_specificity": avg_spec,
            "n_actionable": n_action,
            "themes": themes,
        },
        "analyzer": analyzer.name,
        "errors": errors,
    }
