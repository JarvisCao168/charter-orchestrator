"""LLM diff-level code completion / rewrite for PR comments (v2.8).

Lifts `charter/pr_autosuggest.py` (comment-level rewrites / followups /
action items) to the **diff** level: given a PR's changed files + the
comments on them, propose *concrete code completions / rewrites* per
hunk, not just prose suggestions. The output is a set of patch-shaped
proposals a reviewer can copy straight into the PR.

    - `HunkProposal` - one diff-level suggestion: {file, hunk, context,
      before, after, rationale, analyzer}.
    - `DiffContext` - the input: {file, hunk: {context, before, after},
      comments: [...]}.
    - `HeuristicDiffCompleter` - offline: turns a negative/vague comment
      on a hunk into a targeted `after` rewrite using the comment's
      action verbs + the hunk's before/after lines (no LLM, no key).
    - `LLMDiffCompleter` - Agnes/OpenAI: a structured prompt over the
      hunk + its comments -> a `before`/`after` code rewrite + rationale.
    - `complete_diff_hunks(hunks, ...)` - batch: run the completer over
      a PR's hunks + their comments, returning the proposals.

Stdlib-only. A key enables the LLM completer; otherwise the heuristic one.
Per-hunk LLM failure degrades that hunk to the heuristic proposal (never
raises).
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

__all__ = [
    "HunkProposal", "HeuristicDiffCompleter", "LLMDiffCompleter",
    "complete_diff_hunks", "pick_diff_completer",
]

_ACTION_VERBS = {"move", "moved", "add", "added", "remove", "removed",
                 "fix", "fixed", "refactor", "rename", "update",
                 "replace", "extract", "split", "cache", "validate",
                 "guard", "test", "check", "ensure", "prevent", "avoid",
                 "make", "use", "delete", "bump", "pin", "document",
                 "return", "raise", "wrap", "should", "could"}


@dataclass
class HunkProposal:
    file: str
    hunk_id: str
    context: str
    before: str
    after: str
    rationale: str
    comments: List[str] = field(default_factory=list)
    analyzer: str = "heuristic"

    def as_patch(self) -> str:
        """A minimal unified-diff-shaped snippet the reviewer can drop in."""
        lines = [f"--- a/{self.file}", f"+++ b/{self.file}",
                 f"@@@ hunk {self.hunk_id} @@@"]
        for ln in self.before.splitlines():
            if ln.strip():
                lines.append("-" + ln)
        for ln in self.after.splitlines():
            if ln.strip():
                lines.append("+" + ln)
        lines.append(f"# rationale: {self.rationale}")
        return "\n".join(lines)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file, "hunk_id": self.hunk_id,
            "context": self.context, "before": self.before,
            "after": self.after, "rationale": self.rationale,
            "comments": self.comments, "analyzer": self.analyzer,
            "patch": self.as_patch(),
        }


class _Completer(Protocol):
    name: str
    def complete(self, file: str, hunk_id: str, context: str,
                 before: str, after: str,
                 comments: List[str]) -> Dict[str, Any]:
        """-> {before, after, rationale} (a targeted rewrite of the hunk)."""
        ...


class HeuristicDiffCompleter:
    """Offline diff-level completer: turn a hunk's comments into a
    targeted rewrite using the action verbs present in the comments."""

    name = "heuristic-diff"

    def complete(self, file: str, hunk_id: str, context: str,
                 before: str, after: str,
                 comments: List[str]) -> Dict[str, Any]:
        text = " ".join(comments).lower()
        verbs = [w for w in text.split() if w in _ACTION_VERBS]
        concerns = [w for w in text.split()
                    if w in ("bug", "broken", "unsafe", "insecure",
                             "races", "race", "leak", "wrong")]
        # build a targeted `after` from the before + the implied change
        improved = after or before
        rationale = "no change needed"
        # if a comment asks to move/extract/validate, append a concrete
        # guard / test / refactor line as a suggestion (comment form)
        added_lines: List[str] = []
        if "move" in verbs or "extract" in verbs:
            added_lines.append("# TODO(extract): pull this into a helper "
                               "(per review)")
        if "validate" in verbs or "guard" in verbs:
            added_lines.append("# TODO(guard): add input validation before "
                               "this block")
        if "test" in verbs or "check" in verbs:
            added_lines.append("# TODO(test): add a unit test for this "
                               "hunk")
        if concerns:
            added_lines.append("# CONCERN: " + ", ".join(concerns[:3])
                               + " — address before merge")
        if added_lines:
            improved = (improved.rstrip() + "\n"
                        + "\n".join(added_lines)).strip()
            rationale = ("apply review feedback: "
                         + ", ".join((verbs + concerns)[:4]))
        return {"before": before, "after": improved,
                "rationale": rationale}


class LLMDiffCompleter:
    """Real LLM diff-level completer (Agnes/OpenAI)."""

    name = "llm-diff"

    def __init__(self, api_key: str, model: str, base_url: str,
                 timeout: int = 60) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, file: str, hunk_id: str, context: str,
                 before: str, after: str,
                 comments: List[str]) -> Dict[str, Any]:
        sys_prompt = (
            "You are a senior code reviewer. Given a PR hunk (before/after) "
            "and its review comments, return a *targeted* rewrite that "
            "applies the feedback. Respond ONLY with JSON: "
            '{"before": "<code>", "after": "<improved code>", '
            '"rationale": "<why, <=30 words>"}'
        )
        user = json.dumps({
            "file": file, "hunk": hunk_id, "context": context,
            "before": before, "after": after,
            "comments": comments[:10],
        }, ensure_ascii=False, default=str)
        if len(user) > 6000:
            user = user[:6000] + "...(truncated)"
        body = json.dumps({
            "model": self.model, "temperature": 0.1,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user + "\nReturn the JSON."},
            ],
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        s, e = content.find("{"), content.rfind("}")
        if s != -1 and e != -1 and e > s:
            content = content[s:e + 1]
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            raw = {}
        return {
            "before": str(raw.get("before", before)),
            "after": str(raw.get("after", after)),
            "rationale": str(raw.get("rationale", ""))[:300],
        }


def pick_diff_completer(backend: Optional[str] = None,
                        api_key: Optional[str] = None) -> _Completer:
    """Pick a diff completer. None auto-detects: key -> llm, else
    heuristic."""
    backend = backend or os.environ.get("PR_DIFF_COMPLETER")
    if backend is None:
        if api_key or os.environ.get("AGNES_API_KEY") or \
           os.environ.get("OPENAI_API_KEY"):
            backend = "llm"
        else:
            backend = "heuristic"
    if backend == "heuristic":
        return HeuristicDiffCompleter()
    if backend == "llm":
        key = api_key or os.environ.get("AGNES_API_KEY") or \
            os.environ.get("OPENAI_API_KEY") or ""
        model = os.environ.get("AGNES_MODEL", "agnes-2.5-flash")
        base_url = os.environ.get(
            "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
        return LLMDiffCompleter(key, model, base_url)
    raise ValueError(f"unknown diff completer backend: {backend!r}")


def complete_diff_hunks(
        hunks: List[Dict[str, Any]],
        backend: Optional[str] = None,
        api_key: Optional[str] = None,
        max_hunks: int = 40) -> Dict[str, Any]:
    """tool: complete_diff_hunks - batch diff-level completion over a PR's
    hunks.

    `hunks` is a list of
    {"file","hunk_id","context","before","after","comments":[...]}
    (the shape a PR diff + review comments produce). Returns
    {"n","proposals":[HunkProposal.as_dict],"counts",
     "by_analyzer"}.
    """
    completer = pick_diff_completer(backend, api_key)
    fallback = HeuristicDiffCompleter()
    proposals: List[HunkProposal] = []
    counts = {"proposals": 0, "llm": 0, "heuristic": 0}
    by_analyzer: Dict[str, int] = {}
    for i, h in enumerate(hunks[:max_hunks]):
        file = h.get("file", "")
        hid = h.get("hunk_id", f"hunk-{i}")
        ctx = h.get("context", "")
        before = h.get("before", "")
        after = h.get("after", "")
        comments = h.get("comments", [])
        try:
            out = completer.complete(file, hid, ctx, before, after,
                                     comments)
            analyzer = completer.name
        except Exception:
            out = fallback.complete(file, hid, ctx, before, after,
                                    comments)
            analyzer = "heuristic-fallback"
        prop = HunkProposal(
            file=file, hunk_id=hid, context=ctx,
            before=out.get("before", before),
            after=out.get("after", after),
            rationale=out.get("rationale", ""),
            comments=comments, analyzer=analyzer)
        proposals.append(prop)
        counts["proposals"] += 1
        counts["llm" if "llm" in analyzer else "heuristic"] += 1
        by_analyzer[analyzer] = by_analyzer.get(analyzer, 0) + 1
    return {
        "n": len(proposals),
        "proposals": [p.as_dict() for p in proposals],
        "counts": counts,
        "by_analyzer": by_analyzer,
        "analyzer": completer.name,
    }
