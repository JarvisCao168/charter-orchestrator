"""Cross-session memory LLM summary compression (v2.4).

Lifts `charter/session_store.py` (raw episodic recall) to a **compressed
long-term memory**: after a session ends (or on a salience threshold), its
episodes are summarized into a small set of *facts* that are stored with a
higher salience, so a future session recalls the *distilled* knowledge
instead of re-reading hundreds of raw episodes.

    session_store.remember(...)   raw episodes
            |
            v  (summarize_session / compress)
    MemoryCompressor  -> key facts + one-line summary, higher salience
            |
            v
    session_store.remember(..., kind="summary")  -> cross-session recall

The summarizer is pluggable:
    - `LLMSummarizer` - real LLM call (Agnes/OpenAI) when a key is set
    - `HeuristicSummarizer` - offline deterministic extraction (longest /
      most salient / decision + fact prefixes), used in CI and when no key

Stdlib-only. Offline-safe: `compress(..., online=True)` degrades to the
heuristic summarizer with `details["summarizer"]="heuristic"` when no key
is configured or the call fails.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .session_store import SessionStore

__all__ = [
    "Summarizer", "HeuristicSummarizer", "LLMSummarizer",
    "MemoryCompressor", "compress_session", "pick_summarizer",
]

_SUMMARY_PROMPT = (
    "Compress the following agent session episodes into a short set of key "
    "facts. Return ONLY JSON: {\"facts\": [\"...\"], \"summary\": \"...\"}. "
    "Each fact <= 140 chars. No prose outside the JSON."
)


class Summarizer(Protocol):
    name: str
    def summarize(self, episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """-> {'facts': [..], 'summary': str}"""
        ...


class HeuristicSummarizer:
    """Deterministic, offline summarizer (no LLM / no key)."""

    name = "heuristic"

    def __init__(self, max_facts: int = 8, max_len: int = 140) -> None:
        self.max_facts = max_facts
        self.max_len = max_len

    def summarize(self, episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        # rank by salience then length; keep the most salient / longest
        ranked = sorted(episodes,
                        key=lambda e: (e.get("salience", 1.0),
                                       len(e.get("content", ""))),
                        reverse=True)
        facts: List[str] = []
        for e in ranked:
            content = (e.get("content") or "").strip()
            if not content:
                continue
            if len(content) > self.max_len:
                content = content[:self.max_len].rstrip() + "..."
            # tag with the episode kind for downstream relevance
            facts.append(f"[{e.get('kind', 'episodic')}] {content}")
            if len(facts) >= self.max_facts:
                break
        joined = " | ".join(f[:120] for f in facts[:3])
        summary = (f"{len(episodes)} episodes compressed into {len(facts)} facts. "
                   f"Top: {joined}") if facts else "empty session"
        return {"facts": facts, "summary": summary}


class LLMSummarizer:
    """Real LLM summarizer (Agnes/OpenAI). Provider-agnostic OpenAI-compatible
    chat endpoint over stdlib urllib."""

    name = "llm"

    def __init__(self, api_key: str, model: str, base_url: str,
                 backend: str = "llm", timeout: int = 60,
                 max_facts: int = 8) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.backend = backend
        self.timeout = timeout
        self.max_facts = max_facts

    def _prompt(self, episodes: List[Dict[str, Any]]) -> str:
        blob = json.dumps(
            [{"content": e.get("content", ""), "kind": e.get("kind", ""),
              "salience": e.get("salience", 1.0)} for e in episodes],
            ensure_ascii=False, default=str)
        if len(blob) > 6000:
            blob = blob[:6000] + "...(truncated)"
        return f"Episodes:\n{blob}\n\nReturn the JSON now."

    def summarize(self, episodes: List[ Dict[str, Any]]) -> Dict[str, Any]:
        body = json.dumps({
            "model": self.model, "temperature": 0.0,
            "messages": [
                {"role": "system", "content": _SUMMARY_PROMPT},
                {"role": "user", "content": self._prompt(episodes)},
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
        facts = [str(f)[:140] for f in raw.get("facts", [])
                 if str(f).strip()][:self.max_facts]
        summary = str(raw.get("summary", ""))[:300] or \
            f"{len(episodes)} episodes summarized."
        return {"facts": facts, "summary": summary}


def pick_summarizer(backend: Optional[str] = None,
                     api_key: Optional[str] = None) -> Summarizer:
    """Pick a summarizer. backend in {"llm","heuristic",None}; None auto."""
    backend = backend or os.environ.get("SUMMARIZER")
    if backend is None:
        if api_key or os.environ.get("AGNES_API_KEY") or \
           os.environ.get("OPENAI_API_KEY"):
            backend = "llm"
        else:
            backend = "heuristic"
    if backend == "heuristic":
        return HeuristicSummarizer()
    if backend == "llm":
        key = api_key or os.environ.get("AGNES_API_KEY") or \
            os.environ.get("OPENAI_API_KEY") or ""
        model = os.environ.get("AGNES_MODEL", "agnes-2.5-flash")
        base_url = os.environ.get(
            "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
        return LLMSummarizer(key, model, base_url,
                              backend="agnes" if os.environ.get("AGNES_API_KEY")
                              else "openai")
    raise ValueError(f"unknown summarizer backend: {backend!r}")


class MemoryCompressor:
    """Compress a session's episodes into summary facts, store them back
    into a SessionStore so cross-session recall surfaces the distilled
    knowledge."""

    def __init__(self, store: SessionStore,
                 summarizer: Optional[Summarizer] = None,
                 summary_salience: float = 2.0,
                 max_episodes: int = 200) -> None:
        self.store = store
        self.summarizer = summarizer or HeuristicSummarizer()
        self.summary_salience = summary_salience
        self.max_episodes = max_episodes

    def compress(self, session_id: str, agent_id: str,
                 online: bool = True) -> Dict[str, Any]:
        """Compress one session's raw episodes into summary + facts.

        When online=True a live LLM summarizer is used if configured; any
        failure (or no key) degrades to the heuristic summarizer and the
        result flags details["summarizer"]. Summary facts are written back
        into the same session with kind='summary' + higher salience.
        """
        eps = self.store.recall(agent_id, "all", session_id=session_id,
                                limit=self.max_episodes)
        if not eps:
            return {"session_id": session_id, "episodes": 0,
                    "facts": [], "summary": "empty", "summarizer": "none"}
        # only compress raw episodes (not prior summaries) to avoid
        # compounding
        raw = [e for e in eps if e.get("kind") != "summary"]
        raw = raw or eps
        raw = raw[:self.max_episodes]

        summarizer = self.summarizer
        if online and isinstance(summarizer, HeuristicSummarizer):
            # try to upgrade to a live one if a key is now available
            candidate = pick_summarizer("llm")
            if isinstance(candidate, LLMSummarizer):
                summarizer = candidate

        result: Dict[str, Any]
        try:
            out = summarizer.summarize(raw)
            result = {
                "session_id": session_id, "episodes": len(raw),
                "facts": out["facts"], "summary": out["summary"],
                "summarizer": summarizer.name, "fallback": False,
            }
        except Exception as exc:
            # degrade to heuristic
            hs = HeuristicSummarizer()
            out = hs.summarize(raw)
            result = {
                "session_id": session_id, "episodes": len(raw),
                "facts": out["facts"], "summary": out["summary"],
                "summarizer": "heuristic", "fallback": True,
                "fallback_reason": str(exc)[:200],
            }

        # write summary back
        for fact in result["facts"]:
            self.store.remember(session_id, agent_id, fact,
                                kind="summary",
                                salience=self.summary_salience)
        self.store.remember(session_id, agent_id, result["summary"],
                            kind="summary",
                            salience=self.summary_salience)
        return result


def compress_session(store: SessionStore, session_id: str, agent_id: str,
                     online: bool = True,
                     summarizer: Optional[Summarizer] = None) -> Dict[str, Any]:
    """tool: compress_session - one-shot session compression (v2.4)."""
    mc = MemoryCompressor(store, summarizer=summarizer)
    return mc.compress(session_id, agent_id, online=online)
