"""LLM auto-completion / rewrite suggestions for PR comments (v2.7).

Lifts `charter/pr_sentiment.py` (analyzing comment sentiment /
specificity) to *generating* suggestions: given a PR review comment,
propose concrete follow-ups.

    - `pr_autosuggest(...)` - one-shot: take a comment and return
      {rewrites: [...], followups: [...], action_items: [...]}. A
      rewrite rephrases a vague comment into an actionable one; a
      followup is a question the reviewer likely wants to ask; an
      action_item is a concrete to-do.
    - `HeuristicSuggester` - offline deterministic fallback (turns
      negative/vague comments into action items via keyword + length
      heuristics).
    - `LLMSuggester` - Agnes/OpenAI: a structured prompt over the
      comment text.

Stdlib-only. Pluggable like `pr_sentiment`: a key enables the LLM
suggester, otherwise the heuristic one. `pr_autosuggest` never raises
on a per-comment LLM failure (it degrades that comment to the heuristic
suggestion).
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

__all__ = [
    "Suggester", "HeuristicSuggester", "LLMSuggester",
    "pr_autosuggest", "autosuggest_pr_comments", "pick_suggester",
]


@dataclass
class Suggestion:
    comment_id: int
    user: str
    text: str
    rewrites: List[str] = field(default_factory=list)
    followups: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    analyzer: str = "heuristic"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "comment_id": self.comment_id, "user": self.user,
            "text": self.text,
            "rewrites": self.rewrites,
            "followups": self.followups,
            "action_items": self.action_items,
            "analyzer": self.analyzer,
        }


class Suggester(Protocol):
    name: str
    def suggest(self, text: str) -> Dict[str, Any]:
        """-> {rewrites:[], followups:[], action_items:[]}"""
        ...


class HeuristicSuggester:
    """Offline deterministic suggestions (keyword + length heuristics)."""

    name = "heuristic"

    def suggest(self, text: str) -> Dict[str, Any]:
        low = text.lower()
        words = low.split()
        rewrites: List[str] = []
        followups: List[str] = []
        action_items: List[str] = []

        # vague short comments get a "be specific" rewrite
        if len(words) < 8:
            rewrites.append(
                "Could you point to the specific file/line and describe the "
                "expected behaviour? (e.g. \"in X, Y fails when Z\")")

        # negatives / concerns -> action items
        concerns = [w for w in words
                    if w in ("bad", "wrong", "broken", "bug", "issue",
                             "fail", "failing", "concern", "risk",
                             "insecure", "leak", "unsafe", "hmm")]
        if concerns:
            action_items.append(
                f"Address the concern(s): {', '.join(concerns[:3])}")
            followups.append("What is the minimal repro / test that "
                             "covers this case?")

        # actionable-verb comments -> a structured action item
        verbs = [w for w in words
                 if w in ("should", "could", "move", "add", "remove",
                           "fix", "refactor", "rename", "update",
                           "replace", "extract", "cache", "validate",
                           "guard", "test", "check", "ensure",
                           "prevent", "avoid", "make", "use", "delete",
                           "bump", "pin", "document")]
        if verbs and not concerns:
            action_items.append(
                "Apply the suggested change: " + " ".join(verbs[:4]))

        # code snippets -> a followup asking about edge cases
        if "```" in text or "`" in text:
            followups.append("Edge cases considered? (empty input, "
                             "concurrency, timeout)")

        # approvals -> a lightweight followup about test coverage
        if any(w in ("lgtm", "approved", "great", "clean", "solid",
                     "awesome") for w in words):
            followups.append("Any remaining risks or follow-up tasks?")

        # cap
        return {"rewrites": rewrites[:2], "followups": followups[:3],
                "action_items": action_items[:3]}


class LLMSuggester:
    """Real LLM auto-suggester (Agnes/OpenAI)."""

    name = "llm"

    def __init__(self, api_key: str, model: str, base_url: str,
                 timeout: int = 60) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def suggest(self, text: str) -> Dict[str, Any]:
        sys_prompt = (
            "You are a senior code reviewer. Given a review comment, "
            "suggest: (1) up to 2 rewrites that make it more specific, "
            "(2) up to 3 follow-up questions the reviewer should ask, "
            "(3) up to 3 concrete action items. Return ONLY JSON: "
            '{"rewrites": [...], "followups": [...], '
            '"action_items": [...]}. No prose outside the JSON.'
        )
        body = json.dumps({
            "model": self.model, "temperature": 0.2,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user",
                 "content": f"Comment:\n{text[:1500]}\n\nReturn the JSON."},
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
        def _clean(k: str, cap: int) -> List[str]:
            vals = raw.get(k, [])
            if not isinstance(vals, list):
                vals = [vals]
            return [str(v)[:200] for v in vals if str(v).strip()][:cap]
        return {
            "rewrites": _clean("rewrites", 2),
            "followups": _clean("followups", 3),
            "action_items": _clean("action_items", 3),
        }


def pick_suggester(backend: Optional[str] = None,
                   api_key: Optional[str] = None,
                   prefer_offline: bool = True) -> Suggester:
    """Pick a suggester.

    Offline-first (deterministic, keeps CI green): when ``prefer_offline`` is
    True (default) the heuristic suggester is returned unless the caller
    explicitly asks for the LLM backend via ``backend="llm"``. An LLM
    suggester is used only when ``prefer_offline`` is False AND a key is
    present. This mirrors the multi-agent design analysis' "don't let a
    CI-injected key silently switch to a network backend".
    """
    backend = backend or os.environ.get("PR_SUGGESTER")
    explicit_llm = (backend == "llm")
    if backend is None or not explicit_llm:
        want_llm = (not prefer_offline) and bool(api_key or os.environ.get("AGNES_API_KEY")
                                                 or os.environ.get("OPENAI_API_KEY"))
        backend = "llm" if want_llm else "heuristic"
    if backend == "heuristic":
        return HeuristicSuggester()
    if backend == "llm":
        key = api_key or os.environ.get("AGNES_API_KEY") or \
            os.environ.get("OPENAI_API_KEY") or ""
        model = os.environ.get("AGNES_MODEL", "agnes-2.5-flash")
        base_url = os.environ.get(
            "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
        return LLMSuggester(key, model, base_url)
    raise ValueError(f"unknown suggester backend: {backend!r}")


def pr_autosuggest(text: str,
                   comment_id: int = 0,
                   user: str = "",
                   backend: Optional[str] = None,
                   api_key: Optional[str] = None) -> Suggestion:
    """tool: pr_autosuggest - one comment's rewrites / followups / action
    items."""
    suggester = pick_suggester(backend, api_key)
    out = suggester.suggest(text)
    return Suggestion(
        comment_id=comment_id, user=user, text=text,
        rewrites=out.get("rewrites", []),
        followups=out.get("followups", []),
        action_items=out.get("action_items", []),
        analyzer=suggester.name)


def autosuggest_pr_comments(comments: List[Dict[str, Any]],
                            backend: Optional[str] = None,
                            api_key: Optional[str] = None,
                            max_comments: int = 30
                            ) -> Dict[str, Any]:
    """tool: autosuggest_pr_comments - batch auto-suggest over a list of
    comment dicts ({id, user, body}). Returns {n, suggestions:[...],
    counts:{rewrites, followups, action_items}}.
    """
    suggester = pick_suggester(backend, api_key)
    fallback = HeuristicSuggester()
    suggestions: List[Suggestion] = []
    counts = {"rewrites": 0, "followups": 0, "action_items": 0}
    for i, c in enumerate(comments[:max_comments]):
        text = c.get("body", "") or c.get("text", "")
        cid = c.get("id", i)
        user = (c.get("user") or {}).get("login", "") if isinstance(
            c.get("user"), dict) else c.get("user", "unknown")
        try:
            out = suggester.suggest(text)
            s = Suggestion(comment_id=cid, user=user, text=text,
                            rewrites=out.get("rewrites", []),
                            followups=out.get("followups", []),
                            action_items=out.get("action_items", []),
                            analyzer=suggester.name)
        except Exception:
            out = fallback.suggest(text)
            s = Suggestion(comment_id=cid, user=user, text=text,
                            rewrites=out.get("rewrites", []),
                            followups=out.get("followups", []),
                            action_items=out.get("action_items", []),
                            analyzer="heuristic-fallback")
        suggestions.append(s)
        counts["rewrites"] += len(s.rewrites)
        counts["followups"] += len(s.followups)
        counts["action_items"] += len(s.action_items)
    return {
        "n": len(suggestions),
        "suggestions": [s.as_dict() for s in suggestions],
        "counts": counts,
        "analyzer": suggester.name,
    }
