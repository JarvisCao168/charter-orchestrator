"""Vector memory (v2.0): semantic recall via hash-embeddings.

Upgrades the v1.1 SQLite keyword recall (`charter/memory.py`) to true
semantic recall. Uses a deterministic bag-of-ngrams + hashing trick to map
text to a fixed-dim vector (stdlib only - no numpy), then cosine similarity.

The `embed` hook is pluggable: pass any (text, dim) -> List[float] to use a
real embedding model (e.g. an LLM) at v2.1; the default is the offline
hashing embedder which needs no network and works in CI.
"""
from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
import time
from typing import Any, Callable, Dict, List, Optional, Sequence


DIM = 256  # default embedding dimension

HashEmbedFn = Callable[[str, int], List[float]]


def hash_embed(text: str, dim: int = DIM, n: int = 2) -> List[float]:
    """Deterministic hashing-trick embedder (stdlib only, offline).

    Splits text into word-level and n-gram features, hashes each into `dim`
    buckets with sign hashing, then L2-normalizes. Good enough for semantic
    ranking of short agent memories; swap for an LLM embedder via `embed=`.
    """
    vec = [0.0] * dim
    toks = [t for t in text.lower().replace("\n", " ").split() if t]
    # word features
    features: List[str] = list(toks)
    # n-gram features
    for k in range(2, n + 1):
        for i in range(len(toks) - k + 1):
            features.append("_".join(toks[i:i + k]))
    for feat in features:
        h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if (h[4] & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class VectorMemory:
    """SQLite-persisted vector memory with semantic + recency + salience ranking."""

    def __init__(self, path: str = ":memory:",
                 dim: int = DIM,
                 embed: Optional[HashEmbedFn] = None,
                 table: str = "mem_vectors") -> None:
        self.dim = dim
        self.embed = embed or hash_embed
        self.table = table
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                content TEXT,
                kind TEXT,
                ts REAL,
                salience REAL DEFAULT 1.0,
                vec BLOB NOT NULL)"""
        )
        self._conn.commit()

    # -- persistence helpers --
    @staticmethod
    def _pack(vec: List[float]) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def _unpack(blob: bytes) -> List[float]:
        n = len(blob) // 4
        return list(struct.unpack(f"{n}f", blob))

    # -- API --
    def remember(self, agent_id: str, content: str,
                 kind: str = "episodic", salience: float = 1.0) -> int:
        vec = self.embed(content, self.dim)
        cur = self._conn.execute(
            f"INSERT INTO {self.table} "
            "(agent_id, content, kind, ts, salience, vec) VALUES (?,?,?,?,?,?)",
            (agent_id, content, kind, time.time(), salience, self._pack(vec)),
        )
        self._conn.commit()
        return cur.lastrowid

    def recall(self, agent_id: str, query: str,
               limit: int = 5,
               alpha_recency: float = 0.2,
               alpha_salience: float = 0.3) -> List[Dict[str, Any]]:
        """Semantic recall: score = (1-a-r-s)*cosine + a*recency + r*salience."""
        qvec = self.embed(query, self.dim)
        rows = self._conn.execute(
            f"SELECT id, kind, content, ts, salience, vec FROM {self.table} "
            "WHERE agent_id=?", (agent_id,)).fetchall()
        if not rows:
            return []
        now = time.time()
        span = max(1.0, now - min(r[3] for r in rows))
        out = []
        for r in rows:
            cos = _cosine(qvec, self._unpack(r[5]))
            recency = 1.0 - (now - r[3]) / span
            sal = r[4]
            score = ((1 - alpha_recency - alpha_salience) * max(cos, 0.0)
                     + alpha_recency * recency + alpha_salience * min(sal, 1.0))
            out.append({
                "id": r[0], "kind": r[1], "content": r[2], "ts": r[3],
                "salience": r[4], "score": round(score, 4),
                "cosine": round(max(cos, 0.0), 4),
            })
        out.sort(key=lambda d: d["score"], reverse=True)
        return out[:limit]

    def count(self, agent_id: Optional[str] = None) -> int:
        if agent_id:
            return self._conn.execute(
                f"SELECT COUNT(*) FROM {self.table} WHERE agent_id=?",
                (agent_id,)).fetchone()[0]
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]


def vector_remember(agent_id: str, content: str, kind: str = "episodic",
                   salience: float = 1.0, store: Optional[VectorMemory] = None,
                   path: str = ":memory:") -> int:
    s = store or VectorMemory(path)
    return s.remember(agent_id, content, kind, salience)


def vector_recall(agent_id: str, query: str, limit: int = 5,
                  store: Optional[VectorMemory] = None,
                  path: str = ":memory:") -> List[Dict[str, Any]]:
    """v2.0 semantic recall - replaces v1.1 keyword recall for fuzzy queries."""
    s = store or VectorMemory(path)
    return s.recall(agent_id, query, limit)
