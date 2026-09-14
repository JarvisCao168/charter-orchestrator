"""Production embedding endpoint + cache layer (v2.3).

Sits on top of `charter/llm_embed.py` (Agnes/OpenAI embedders) and adds two
production-grade properties that the bare HTTP embedder lacks:

    1. **Caching** - in-memory LRU + optional on-disk SQLite store keyed by
       (backend, model, dim, sha256(text)). Re-embedding the same text is O(1),
       so repeated recalls / batch indexing don't hammer the API and don't
       burn tokens.
    2. **Production endpoint wiring** - `production_embedder(...)` returns a
       ready-to-use `Embedder` that points at a *named* endpoint
       ("agnes" / "openai" / a custom OpenAI-compatible URL) read from env,
       with the cache bound in, plus a **graceful fallback** to the offline
       hashing embedder when no key / no network, so the pipeline keeps
       working in CI.

Stdlib-only (urllib + hashlib + sqlite3 + functools). No new hard deps.

Env vars (same as llm_embed.py):
    AGNES_API_KEY / AGNES_BASE_URL / AGNES_MODEL
    OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
    EMBED_CACHE_PATH   optional SQLite path for the disk cache
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from .vector_memory import hash_embed, DIM

# Optional: reuse the real HTTP embedders when available (same package).
try:
    from .llm_embed import AgnesEmbedder, OpenAIEmbedder
    HAS_LLM_EMBED = True
except Exception:
    HAS_LLM_EMBED = False

__all__ = [
    "EmbedCache", "CachedEmbedder", "production_embedder", "embed_with_cache",
]


class EmbedCache:
    """Two-level embed cache: in-memory LRU + optional SQLite disk store."""

    def __init__(self, lru_size: int = 4096,
                 disk_path: Optional[str] = None) -> None:
        self.lru_size = lru_size
        self._mem: "OrderedDict[str, List[float]]" = OrderedDict()
        self._lock = threading.Lock()
        self._db: Optional[sqlite3.Connection] = None
        if disk_path:
            self._disk_path = disk_path or os.environ.get("EMBED_CACHE_PATH")
            if self._disk_path:
                os.makedirs(os.path.dirname(self._disk_path) or ".",
                            exist_ok=True)
                self._db = sqlite3.connect(self._disk_path,
                                           check_same_thread=False)
                self._db.execute("PRAGMA journal_mode=WAL")
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS embed_cache ("
                    "cache_key TEXT PRIMARY KEY, backend TEXT, model TEXT,"
                    " dim INTEGER, vector TEXT, hits INTEGER DEFAULT 0)")
                self._db.commit()

    @staticmethod
    def _key(backend: str, model: str, dim: int, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
        return f"{backend}|{model}|{dim}|{digest}"

    def _lru_get(self, key: str) -> Optional[List[float]]:
        with self._lock:
            if key in self._mem:
                self._mem.move_to_end(key)
                return list(self._mem[key])
            return None

    def _lru_set(self, key: str, vec: List[float]) -> None:
        with self._lock:
            self._mem[key] = vec
            self._mem.move_to_end(key)
            while len(self._mem) > self.lru_size:
                self._mem.popitem(last=False)

    def _disk_get(self, key: str) -> Optional[List[float]]:
        if not self._db:
            return None
        row = self._db.execute(
            "SELECT vector FROM embed_cache WHERE cache_key=?", (key,)).fetchone()
        if row:
            self._db.execute(
                "UPDATE embed_cache SET hits=hits+1 WHERE cache_key=?", (key,))
            self._db.commit()
            return json.loads(row[0])
        return None

    def _disk_set(self, key: str, backend: str, model: str,
                  dim: int, vec: List[float]) -> None:
        if not self._db:
            return
        self._db.execute(
            "INSERT OR REPLACE INTO embed_cache "
            "(cache_key, backend, model, dim, vector) VALUES (?,?,?,?,?)",
            (key, backend, model, dim, json.dumps(vec)))
        self._db.commit()

    def get(self, key: str) -> Optional[List[float]]:
        v = self._lru_get(key)
        if v is not None:
            return v
        v = self._disk_get(key)
        if v is not None:
            self._lru_set(key, v)
            return v
        return None

    def put(self, key: str, backend: str, model: str, dim: int,
            vec: List[float]) -> None:
        self._lru_set(key, vec)
        self._disk_set(key, backend, model, dim, vec)

    def stats(self) -> Dict[str, Any]:
        return {
            "mem_hits": len(self._mem),
            "mem_capacity": self.lru_size,
            "disk_enabled": self._db is not None,
        }


class CachedEmbedder:
    """An `Embedder` that wraps any underlying embedder with an EmbedCache.

    Exposes the `VectorMemory` embedder contract: `embed(text, dim)` and a
    `.dim` attribute. On a cache miss it calls the wrapped embedder and
    stores the result.
    """

    def __init__(self, backend: str, model: str, dim: int,
                 underlying, cache: EmbedCache) -> None:
        self.backend = backend
        self.model = model
        self.dim = dim
        self._underlying = underlying
        self._cache = cache

    def __call__(self, text: str, dim: Optional[int] = None) -> List[float]:
        dim = dim or self.dim
        key = EmbedCache._key(self.backend, self.model, dim, text)
        hit = self._cache.get(key)
        if hit is not None and len(hit) == dim:
            return hit
        vec = self._underlying(text, dim)
        if len(vec) != dim:
            vec = vec[:dim] if len(vec) > dim else vec + [0.0] * (dim - len(vec))
        self._cache.put(key, self.backend, self.model, dim, vec)
        return vec


def production_embedder(
        which: Optional[str] = None,
        dim: int = DIM,
        cache: Optional[EmbedCache] = None,
        disk_cache: bool = True,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None) -> CachedEmbedder:
    """tool: production_embedder - wire a named production embedding endpoint.

    `which` in {"agnes","openai","hash",None}. Auto-detect order when None:
    AGNES_API_KEY -> agnes, else OPENAI_API_KEY -> openai, else fall back to
    the offline hashing embedder (so the pipeline still works with no key).
    The result is always a CachedEmbedder; a disk cache is enabled by default
    at $EMBED_CACHE_PATH or a temp location.
    """
    cache = cache or EmbedCache(disk_path=(
        os.environ.get("EMBED_CACHE_PATH") or
        os.path.join(os.path.expanduser("~"), ".charter", "embed_cache.db")
    ) if disk_cache else None)

    which = which or os.environ.get("EMBED_WHICH")
    if which is None:
        if os.environ.get("AGNES_API_KEY") or api_key:
            which = "agnes"
        elif os.environ.get("OPENAI_API_KEY"):
            which = "openai"
        else:
            which = "hash"

    if which == "hash":
        return CachedEmbedder("hash", model or "hashing", dim,
                               hash_embed, cache)

    if not HAS_LLM_EMBED:
        raise RuntimeError(
            "charter.llm_embed unavailable; cannot build a live embedder")

    if which == "agnes":
        key = api_key or os.environ.get("AGNES_API_KEY", "")
        underlying = AgnesEmbedder(
            key, model or os.environ.get("AGNES_MODEL", "agnes-embed-1"),
            base_url or os.environ.get(
                "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1"),
            dim=dim)
        return CachedEmbedder("agnes", model or "agnes", dim,
                               underlying, cache)
    elif which == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        underlying = OpenAIEmbedder(
            key, model or os.environ.get(
                "OPENAI_MODEL", "text-embedding-3-small"),
            base_url or os.environ.get(
                "OPENAI_BASE_URL", "https://api.openai.com/v1/embeddings"),
            dim=dim)
        return CachedEmbedder("openai", model or "openai", dim,
                               underlying, cache)
    else:
        raise ValueError(f"unknown embedder 'which': {which!r}")


def embed_with_cache(text: str, which: Optional[str] = None,
                     dim: int = DIM,
                     disk_cache: bool = True) -> Dict[str, Any]:
    """One-shot: embed with a fresh cache + report cache-state.
    Convenience for callers that don't hold a CachedEmbedder instance."""
    emb = production_embedder(which=which, dim=dim, disk_cache=disk_cache)
    vec = emb(text, dim)
    return {"vector": vec, "dim": dim, "backend": emb.backend,
            "model": emb.model, "cache": emb._cache.stats()}
