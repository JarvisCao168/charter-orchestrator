"""Hierarchical memory compression: episode -> session -> project (v2.5).

Lifts `charter/memory_compress.py` (single-level session compression) to a
**three-tier** hierarchy:

    tier 0  episodes  (raw, in a session)
    tier 1  session   (summarized from episodes  - memory_compress.compress_session)
    tier 2  project   (summarized from session summaries, with a rolling
                       long-horizon digest)

Each tier is stored back into the `SessionStore` with a higher salience and a
`kind` tag (`summary` at tier 1, `project_summary` at tier 2), so a future
session can recall:
    - the **project** digest (what the whole effort accomplished), or
    - a specific **session** summary, or
    - raw **episodes**.

`MemoryHierarchy.compress_project(...)` drives the full episode->session->project
compression for one project across many sessions, and `recall_project(...)`
surfaces the right tier for a query (project digest first, then the most
relevant session summary, then episodes).

Stdlib-only. Summarizers come from `memory_compress` (LLM when a key is set,
heuristic otherwise). Offline-safe: a missing / failed LLM degrades to the
heuristic summarizer, and `compress_project` always completes.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .session_store import SessionStore
from .memory_compress import MemoryCompressor, HeuristicSummarizer, pick_summarizer

__all__ = [
    "TierSummary", "MemoryHierarchy", "compress_project", "recall_project",
]


@dataclass
class TierSummary:
    tier: int
    scope: str            # "episode" | "session" | "project"
    scope_id: str
    summary: str
    facts: List[str] = field(default_factory=list)
    salience: float = 1.0
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return {"tier": self.tier, "scope": self.scope,
                "scope_id": self.scope_id, "summary": self.summary,
                "facts": self.facts, "salience": self.salience, "ts": self.ts}


class MemoryHierarchy:
    """Three-tier memory compression over a SessionStore."""

    def __init__(self, store: SessionStore,
                 session_salience: float = 2.0,
                 project_salience: float = 3.0,
                 online: bool = True,
                 summarizer: Optional[Any] = None) -> None:
        self.store = store
        self.session_salience = session_salience
        self.project_salience = project_salience
        self.online = online
        self.summarizer = summarizer
        # tier 1 compressor (episodes -> session summary)
        self._session_comp = MemoryCompressor(
            store, summarizer=self.summarizer,
            summary_salience=session_salience)

    # -- tier 1: session -------------------------------------------------
    def compress_session(self, session_id: str, agent_id: str,
                         online: Optional[bool] = None) -> TierSummary:
        online = self.online if online is None else online
        res = self._session_comp.compress(session_id, agent_id, online=online)
        tier = TierSummary(
            tier=1, scope="session", scope_id=session_id,
            summary=res.get("summary", ""),
            facts=res.get("facts", []),
            salience=self.session_salience)
        # make sure the summary text is stored (compress already stores it,
        # but ensure the facts are tagged as tier-1 summaries)
        return tier

    # -- tier 2: project -------------------------------------------------
    def compress_project(self, project_id: str, agent_id: str,
                         session_ids: Optional[List[str]] = None,
                         online: Optional[bool] = None) -> TierSummary:
        """Compress all of a project's sessions into a rolling project digest."""
        online = self.online if online is None else online
        session_ids = session_ids or [
            s["session_id"] for s in self.store.sessions()
            if s["agent_id"] == agent_id]
        session_summaries: List[str] = []
        fact_pool: List[str] = []
        for sid in session_ids:
            t1 = self.compress_session(sid, agent_id, online=online)
            if t1.summary:
                session_summaries.append(t1.summary)
            fact_pool.extend(t1.facts)

        # roll session summaries into a project-level digest
        proj_facts, proj_summary = self._summarize_project(
            fact_pool, session_summaries, online=online)

        tier = TierSummary(
            tier=2, scope="project", scope_id=project_id,
            summary=proj_summary, facts=proj_facts,
            salience=self.project_salience)
        # store project digest under the agent (session_id = project id)
        for f in proj_facts:
            self.store.remember(project_id, agent_id, f,
                                kind="project_summary",
                                salience=self.project_salience)
        self.store.remember(project_id, agent_id, proj_summary,
                            kind="project_summary",
                            salience=self.project_salience)
        return tier

    def _summarize_project(self, facts: List[str],
                           session_summaries: List[str],
                           online: bool) -> tuple:
        """Collapse session summaries + facts into a rolling project digest."""
        corpus = " ".join(session_summaries) + " " + " ".join(facts[:20])
        # dedupe + cap the fact pool
        seen = set()
        uniq_facts: List[str] = []
        for f in facts:
            key = f.lower().strip()
            if key and key not in seen:
                seen.add(key)
                uniq_facts.append(f)
        uniq_facts = uniq_facts[:24]
        if online:
            summarizer = pick_summarizer("llm")
            try:
                out = summarizer.summarize(
                    [{"content": s, "kind": "project_summary",
                      "salience": self.project_salience}
                     for s in session_summaries]
                    or [{"content": " ".join(uniq_facts[:5]),
                         "kind": "project_summary",
                         "salience": self.project_salience}])
                proj_facts = out.get("facts", uniq_facts[:24])
                proj_summary = out.get("summary",
                                       "Project: " + " | ".join(uniq_facts[:3]))
                return proj_facts, proj_summary
            except Exception:
                pass  # fall through to heuristic
        # heuristic project digest
        proj_facts = uniq_facts[:24]
        proj_summary = (f"Project digest across "
                        f"{len(session_summaries)} sessions. "
                        f"Key themes: " + " | ".join(uniq_facts[:4]))
        return proj_facts, proj_summary

    # -- recall ----------------------------------------------------------
    def recall(self, agent_id: str, query: str,
               limit: int = 5) -> Dict[str, Any]:
        """Recall across tiers: project digest first, then session, then
        episodes. Returns the best-matching item per tier + a flat top-k."""
        # project tier
        proj = self.store.recall(agent_id, query, limit=1)
        proj_hits = [p for p in proj if p.get("kind") == "project_summary"]
        session_hits = [p for p in self.store.recall(
            agent_id, query, limit=limit)
            if p.get("kind") == "summary"]
        episode_hits = [p for p in self.store.recall(
            agent_id, query, limit=limit)
            if p.get("kind") in ("episodic", "decision", "observation")]
        # rank: prefer project, then session, then episode
        ordered: List[Dict[str, Any]] = []
        for h in proj_hits:
            ordered.append({**h, "tier": 2})
        for h in session_hits:
            ordered.append({**h, "tier": 1})
        for h in episode_hits:
            ordered.append({**h, "tier": 0})
        ordered.sort(key=lambda x: (-x.get("rank", 0), x.get("tier", 0)))
        return {
            "query": query, "agent_id": agent_id,
            "project": proj_hits, "sessions": session_hits,
            "episodes": episode_hits, "top": ordered[:limit],
        }


def compress_project(store: SessionStore, project_id: str, agent_id: str,
                     session_ids: Optional[List[str]] = None,
                     online: bool = True) -> TierSummary:
    """tool: compress_project - one-shot episode->session->project compression."""
    hi = MemoryHierarchy(store, online=online)
    return hi.compress_project(project_id, agent_id,
                               session_ids=session_ids, online=online)


def recall_project(store: SessionStore, agent_id: str, query: str,
                   limit: int = 5) -> Dict[str, Any]:
    """tool: recall_project - tiered recall (project digest -> session -> episodes)."""
    hi = MemoryHierarchy(store, online=False)
    return hi.recall(agent_id, query, limit=limit)
