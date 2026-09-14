"""Cross-session persistent memory (v2.2).

Closes the "cross-session recall" gap flagged in the v1.0 peer review.
`MemoryStore` (v1.1) is in-process SQLite; this layer adds a **file-backed,
multi-process-safe store** that survives across separate agent sessions and
supports true semantic recall by reusing the `VectorMemory` embedder.

Design:
    - One SQLite file per "agent home" (default `~/.charter/sessions.db`).
    - `remember(...)` appends an episode; `recall(...)` ranks by a blend of
      recency + salience + semantic similarity (cosine over the embedder's
      vectors, stored alongside each memory so recall is O(1)-per-candidate
      rather than re-embedding the corpus on every query).
    - A `query(...)` with a free-text `query` triggers semantic search across
      *all* agent ids (cross-session), so a new session can surface what a
      previous session learned.

Stdlib only; `embed` is pluggable exactly like `VectorMemory` (default is the
offline hashing embedder, so no network/key needed in CI).
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional

from .vector_memory import VectorMemory, hash_embed, DIM

__all__ = ["SessionStore", "DEFAULT_DB"]

DEFAULT_DB = os.path.join(
    os.path.expanduser("~"), ".charter", "sessions.db")


class SessionStore:
    """File-backed, multi-process cross-session memory with semantic recall."""

    def __init__(self, path: Optional[str] = None,
                 embed: Optional[Callable[[str, int], List[float]]] = None,
                 dim: int = DIM) -> None:
        self.path = path or DEFAULT_DB
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.embed = embed or hash_embed
        self.dim = dim
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
              session_id  TEXT PRIMARY KEY,
              agent_id    TEXT,
              created_ts  REAL,
              summary     TEXT DEFAULT '')""")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id  TEXT,
              agent_id    TEXT,
              kind        TEXT DEFAULT 'episodic',
              content     TEXT,
              vector      TEXT,
              salience    REAL DEFAULT 1.0,
              ts          REAL)""")
        self._conn.commit()

    # -- sessions ----------------------------------------------------------
    def open_session(self, session_id: str, agent_id: str = "default",
                     summary: str = "") -> str:
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, agent_id, created_ts, summary)"
            " VALUES (?,?,?,?)",
            (session_id, agent_id, time.time(), summary))
        self._conn.commit()
        return session_id

    # -- remember / recall -------------------------------------------------
    def remember(self, session_id: str, agent_id: str, content: str,
                 kind: str = "episodic", salience: float = 1.0) -> int:
        vec = self.embed(content, self.dim)
        cur = self._conn.execute(
            "INSERT INTO episodes (session_id, agent_id, kind, content, vector,"
            " salience, ts) VALUES (?,?,?,?,?,?,?)",
            (session_id, agent_id, kind, content, json.dumps(vec),
             salience, time.time()))
        self._conn.commit()
        return int(cur.lastrowid)

    def _candidates(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if agent_id:
            rows = self._conn.execute(
                "SELECT session_id, agent_id, kind, content, vector, salience, ts"
                " FROM episodes WHERE agent_id = ?", (agent_id,)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT session_id, agent_id, kind, content, vector, salience, ts"
                " FROM episodes").fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append({
                "session_id": r[0], "agent_id": r[1], "kind": r[2],
                "content": r[3], "vector": json.loads(r[4]),
                "salience": r[5], "ts": r[6]})
        return out

    def recall(self, agent_id: str, query: str,
               session_id: Optional[str] = None,
               limit: int = 5) -> List[Dict[str, Any]]:
        """Semantic + recency + salience recall scoped to one agent (or session)."""
        rows = self._candidates(agent_id)
        if session_id:
            rows = [r for r in rows if r["session_id"] == session_id]
        if not rows:
            return []
        qvec = self.embed(query, self.dim)
        import math
        for r in rows:
            dot = sum(a * b for a, b in zip(qvec, r["vector"]))
            denom = (math.sqrt(sum(x * x for x in qvec)) *
                     math.sqrt(sum(x * x for x in r["vector"])) or 1.0)
            r["_sim"] = max(0.0, min(1.0, dot / denom))
        now = time.time()
        # blend: 0.5 semantic + 0.3 recency + 0.2 salience
        for r in rows:
            recency = max(0.0, min(1.0, 1.0 - (now - r["ts"]) / 86400.0))
            r["_rank"] = round(0.5 * r["_sim"] + 0.3 * recency +
                               0.2 * r["salience"], 4)
        rows.sort(key=lambda r: r["_rank"], reverse=True)
        top = rows[:limit]
        return [{"session_id": r["session_id"], "agent_id": r["agent_id"],
                 "kind": r["kind"], "content": r["content"],
                 "similarity": r["_sim"], "rank": r["_rank"]} for r in top]

    def query(self, text: str, limit: int = 5,
              agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Cross-session semantic query (recall across all sessions)."""
        return self.recall(agent_id or "default", text, limit=limit) \
            if agent_id else self._cross_session(text, limit)

    def _cross_session(self, text: str, limit: int = 5) -> List[Dict[str, Any]]:
        rows = self._candidates(None)
        if not rows:
            return []
        import math
        qvec = self.embed(text, self.dim)
        for r in rows:
            dot = sum(a * b for a, b in zip(qvec, r["vector"]))
            denom = (math.sqrt(sum(x * x for x in qvec)) *
                     math.sqrt(sum(x * x for x in r["vector"])) or 1.0)
            r["_sim"] = max(0.0, min(1.0, dot / denom))
            now = time.time()
            recency = max(0.0, min(1.0, 1.0 - (now - r["ts"]) / 86400.0))
            r["_rank"] = round(0.5 * r["_sim"] + 0.3 * recency +
                               0.2 * r["salience"], 4)
        rows.sort(key=lambda r: r["_rank"], reverse=True)
        return [{"session_id": r["session_id"], "agent_id": r["agent_id"],
                 "kind": r["kind"], "content": r["content"],
                 "similarity": r["_sim"], "rank": r["_rank"]}
                for r in rows[:limit]]

    def sessions(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT session_id, agent_id, created_ts, summary FROM sessions"
            " ORDER BY created_ts DESC").fetchall()
        return [{"session_id": r[0], "agent_id": r[1],
                 "created_ts": r[2], "summary": r[3]} for r in rows]

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()
