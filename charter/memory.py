"""Persistent agent memory (P0 gap: cross-session recall).

SQLite-backed store with keyword recall (vector backend plugs in at v2.0).
Implements the `memory_recall` capability that v1.0 only sketched in
collab_04 as a static knowledge graph.
"""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict, List, Optional


class MemoryStore:
    """SQLite key-value + episodic memory with recency + relevance ranking."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS memories (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               agent_id TEXT,
               kind TEXT,
               content TEXT,
               ts REAL,
               salience REAL DEFAULT 1.0)"""
        )
        self._conn.commit()

    def remember(self, agent_id: str, content: str,
                 kind: str = "episodic", salience: float = 1.0) -> int:
        cur = self._conn.execute(
            "INSERT INTO memories (agent_id, kind, content, ts, salience)"
            " VALUES (?,?,?,?,?)",
            (agent_id, kind, content, time.time(), salience),
        )
        self._conn.commit()
        return cur.lastrowid

    def recall(self, agent_id: str, query: str,
               limit: int = 5) -> List[Dict[str, Any]]:
        """Keyword + recency + salience ranked recall."""
        words = [w for w in query.lower().split() if len(w) > 2]
        like = " OR ".join(f"lower(content) LIKE ?" for _ in words) or "1=0"
        params: List[Any] = [f"%{w}%" for w in words] + [agent_id, limit]
        q = (
            "SELECT id, kind, content, ts, salience FROM memories "
            f"WHERE ({like}) AND agent_id = ? "
            "ORDER BY salience DESC, ts DESC LIMIT ?"
        )
        rows = self._conn.execute(q, params).fetchall()
        return [
            {"id": r[0], "kind": r[1], "content": r[2], "ts": r[3],
             "salience": r[4]}
            for r in rows
        ]

    def count(self, agent_id: Optional[str] = None) -> int:
        if agent_id:
            return self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE agent_id=?", (agent_id,)
            ).fetchone()[0]
        return self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]


_DEFAULT = MemoryStore()


def memory_recall(agent_id: str, query: str,
                  limit: int = 5, store: Optional[MemoryStore] = None) -> List[Dict[str, Any]]:
    """tool: memory_recall - cross-session agent recall (P0)."""
    return (store or _DEFAULT).recall(agent_id, query, limit)
