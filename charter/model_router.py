"""Model tier router + semantic result cache for multi-Agent cost control (v3.11).

Implements the "small-model routing + semantic cache" idea from the multi-agent
consistency design analysis: route cheap tasks to a small model and reserve the
expensive model for complex ones, plus cache results so identical (or
semantically near-identical) requests don't re-burn tokens.

Builds on Charter's existing cost tooling (`charter.judge_pool_cost`) and
embedding capability (`charter.semantic_trace.make_embedder` / offline
hashing) so it stays stdlib-safe.

    - `TaskProfile` - complexity signal for a task (depth / fan-in /
      risk / token estimate).
    - `ModelTier` - a named tier (small / medium / large) with a cost weight.
    - `ModelRouter` - scores a task and picks the cheapest tier that
      clears the task's complexity floor.
    - `SemanticCache` - LRU + optional on-disk store keyed by semantic hash,
      with a hit/miss budget.

Stdlib-only; offline-safe.
"""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

__all__ = ["TaskProfile", "ModelTier", "ModelRouter", "SemanticCache",
           "route_task", "DEFAULT_TIERS",
           "SemanticCacheBackend", "HTTPKeyValueBackend", "make_remote_backend"]


# ---------------------------------------------------------------------------
# Task profile + tiers
# ---------------------------------------------------------------------------

@dataclass
class TaskProfile:
    """Complexity signal used to decide which model tier a task needs."""
    depth: int = 1          # DAG depth (number of dependent stages)
    fan_in: int = 1        # number of upstream inputs consumed
    risk: float = 0.0      # 0..1, how consequential a wrong answer is
    tokens: int = 512      # rough prompt/output token budget
    requires_reasoning: bool = False

    def complexity(self) -> float:
        """A 0..100 composite complexity score."""
        score = 0.0
        score += min(self.depth, 10) * 4.0          # up to 40
        score += min(self.fan_in, 5) * 4.0          # up to 20
        score += self.risk * 30.0                    # up to 30
        score += min(self.tokens, 4096) / 4096 * 10.0  # up to 10
        if self.requires_reasoning:
            score += 20.0
        return round(min(score, 100.0), 3)


class ModelTier:
    """A named model tier with a relative cost weight and a complexity floor.

    A task may only be routed to a tier whose ``min_complexity`` is <= the
    task's complexity (never downgrade a complex task to a too-weak tier).
    """

    def __init__(self, name: str, model: str, cost: float = 1.0,
                 min_complexity: float = 0.0) -> None:
        self.name = name
        self.model = model
        self.cost = cost
        self.min_complexity = min_complexity


# Default tier ladder (cheap -> capable). Adjust models to your provider.
DEFAULT_TIERS: List[ModelTier] = [
    ModelTier("small", "small-fast", cost=1.0, min_complexity=0.0),
    ModelTier("medium", "medium-balanced", cost=3.0, min_complexity=40.0),
    ModelTier("large", "large-frontier", cost=10.0, min_complexity=70.0),
]


class ModelRouter:
    """Pick the cheapest model tier that satisfies a task's complexity.

    ``tiers`` must be ordered cheap->capable (ascending ``min_complexity``).
    For a given task the router walks the tiers and selects the cheapest one
    whose ``min_complexity`` does not exceed the task complexity; the
    fallback (no tier qualifies) is the most capable tier.
    """

    def __init__(self, tiers: Optional[List[ModelTier]] = None) -> None:
        self.tiers = sorted(tiers or DEFAULT_TIERS,
                            key=lambda t: t.min_complexity)

    def route(self, profile: TaskProfile) -> Dict[str, Any]:
        complexity = profile.complexity()
        chosen = self.tiers[0]
        for tier in self.tiers:
            if tier.min_complexity <= complexity:
                chosen = tier  # keep the most capable tier that still qualifies
        return {
            "tier": chosen.name,
            "model": chosen.model,
            "cost": chosen.cost,
            "complexity": complexity,
            "reason": (f"complexity={complexity} "
                       f">= min_complexity={chosen.min_complexity}"),
        }

    def cheapest_qualified(self, profile: TaskProfile) -> ModelTier:
        complexity = profile.complexity()
        qualified = [t for t in self.tiers if t.min_complexity <= complexity]
        if not qualified:
            return self.tiers[-1]
        return min(qualified, key=lambda t: t.cost)


def route_task(profile: TaskProfile,
               tiers: Optional[List[ModelTier]] = None) -> Dict[str, Any]:
    """One-shot convenience wrapper around :class:`ModelRouter`."""
    return ModelRouter(tiers).route(profile)


# ---------------------------------------------------------------------------
# Semantic result cache (cost control)
# ---------------------------------------------------------------------------

class SemanticCache:
    """LRU result cache keyed by a semantic hash of the request.

    ``semantic_key`` is a callable ``(request: str) -> str`` used to build the
    lookup key. The default key normalizes the request (lowercase, trimmed
    whitespace) and hashes it with blake2b, so trivially-identical requests
    hit the cache. Supply a semantic-embedding-based key (e.g. via
    ``charter.semantic_trace.make_embedder``) to get near-duplicate hits.

    Bounded by ``max_entries`` (LRU eviction). Thread-safe.

    v3.12: optional on-disk SQLite persistence (``disk_path``). When set,
    every ``put`` is also written to the ``semantic_cache`` table and every
    ``get`` consults disk on an in-memory miss, so the cache survives process
    restarts. Mirrors the two-level LRU+SQLite pattern of
    ``charter.embed_cache.EmbedCache``. No new hard deps (sqlite3 is stdlib).
    """

    def __init__(self,
                 semantic_key: Optional[Any] = None,
                 max_entries: int = 256,
                 disk_path: Optional[str] = None,
                 remote: Optional["SemanticCacheBackend"] = None) -> None:
        self._cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._max_entries = max(1, int(max_entries))
        self._lock = __import__("threading").Lock()
        self._key_fn = semantic_key or _default_semantic_key
        self.hits = 0
        self.misses = 0
        # v3.12: optional SQLite disk store for cross-process persistence.
        self._db: Optional[Any] = None
        self._disk_path = disk_path
        # v3.13: optional remote/distributed L3 backend (offline-safe)
        self._remote = remote
        if disk_path:
            import sqlite3
            import os as _os
            parent = _os.path.dirname(disk_path)
            if parent:
                _os.makedirs(parent, exist_ok=True)
            self._db = sqlite3.connect(disk_path, check_same_thread=False)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS semantic_cache ("
                "cache_key TEXT PRIMARY KEY, value TEXT, ts REAL, hits INTEGER DEFAULT 0)")
            self._db.commit()

    # -- disk helpers ------------------------------------------------
    def _disk_get(self, key: str) -> Optional[Any]:
        if not self._db:
            return None
        row = self._db.execute(
            "SELECT value FROM semantic_cache WHERE cache_key=?", (key,)).fetchone()
        if row:
            self._db.execute(
                "UPDATE semantic_cache SET hits=hits+1 WHERE cache_key=?", (key,))
            self._db.commit()
            import json as _json
            return _json.loads(row[0])
        return None

    def _disk_set(self, key: str, value: Any) -> None:
        if not self._db:
            return
        import json as _json
        self._db.execute(
            "INSERT OR REPLACE INTO semantic_cache (cache_key, value, ts) VALUES (?,?,?)",
            (key, _json.dumps(value, ensure_ascii=False, default=str), time.time()))
        self._db.commit()

    def close(self) -> None:
        """Close the disk store and remote backend (no-ops when disabled)."""
        if self._db is not None:
            self._db.close()
            self._db = None
            self._disk_path = None
        # v3.13: close the remote backend if attached
        if self._remote is not None:
            try:
                self._remote.close()
            except Exception:  # noqa: BLENT
                pass
            self._remote = None

    def is_persistent(self) -> bool:
        """True when an on-disk SQLite store is attached."""
        return self._db is not None

    # -- key --------------------------------------------------------
    def _k(self, request: str) -> str:
        key = self._key_fn(request)
        if isinstance(key, (list, tuple)):
            key = "".join(f"{i}:{v}" for i, v in enumerate(key))
        return str(key)

    # -- operations -------------------------------------------------
    def get(self, request: str) -> Optional[Any]:
        k = self._k(request)
        with self._lock:
            entry = self._cache.get(k)
            if entry is not None:
                self.hits += 1
                self._cache.move_to_end(k)
                return entry["value"]
        # v3.12: memory miss -> consult the on-disk store.
        disk_val = self._disk_get(k)
        if disk_val is not None:
            with self._lock:
                self._cache[k] = {"value": disk_val, "ts": time.time()}
                self._cache.move_to_end(k)
                self.hits += 1
                while len(self._cache) > self._max_entries:
                    self._cache.popitem(last=False)
            return disk_val
        # v3.13: L1+L2 miss -> consult the remote (distributed) backend.
        # Offline-safe: any backend error degrades to a miss, never crashes.
        if self._remote is not None:
            try:
                remote_val = self._remote.get(k)
            except Exception:  # noqa: BLENT
                remote_val = None
            if remote_val is not None:
                with self._lock:
                    self._cache[k] = {"value": remote_val, "ts": time.time()}
                    self._cache.move_to_end(k)
                    self.hits += 1
                    while len(self._cache) > self._max_entries:
                        self._cache.popitem(last=False)
                return remote_val
        with self._lock:
            self.misses += 1
        return None

    def put(self, request: str, value: Any) -> None:
        k = self._k(request)
        with self._lock:
            self._cache[k] = {"value": value, "ts": time.time()}
            self._cache.move_to_end(k)
            while len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)
        # v3.12: mirror to the on-disk store for cross-process persistence.
        self._disk_set(k, value)
        # v3.13: mirror to the remote (distributed) backend; offline-safe.
        if self._remote is not None:
            try:
                self._remote.put(k, value)
            except Exception:  # noqa: BLENT
                pass

    def __contains__(self, request: str) -> bool:
        return self.get(request) is not None or self._k(request) in self._peek()

    def _peek(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._cache)

    def stats(self) -> Dict[str, Any]:
        return {"entries": len(self._cache), "hits": self.hits,
                "misses": self.misses,
                "hit_rate": (self.hits / (self.hits + self.misses)
                             if (self.hits + self.misses) else 0.0),
                "disk_enabled": self.is_persistent(),
                "disk_path": self._disk_path,
                "remote_enabled": self._remote is not None,
                "remote": self._remote.name() if self._remote else None}

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0


def _default_semantic_key(request: str) -> str:
    normalized = " ".join((request or "").lower().split())
    return hashlib.blake2b(normalized.encode("utf-8"), digest_size=16).hexdigest()


# ---------------------------------------------------------------------------
# v3.13: distributed / remote cache backends
# ---------------------------------------------------------------------------

class SemanticCacheBackend:
    """Protocol for pluggable SemanticCache storage layers.

    A backend implements ``get(key) -> Optional[Any]`` and ``put(key, value) -> None``.
    ``close()`` releases resources. Defaults are provided so a concrete class
    only needs to override get/put.
    """

    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError

    def put(self, key: str, value: Any) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def name(self) -> str:
        return "backend"


class HTTPKeyValueBackend(SemanticCacheBackend):
    """Stdlib-only HTTP key-value store backend (JSON over HTTP).

    Works against any service exposing ``GET {base}/kv/{key}`` (200 -> JSON
    value, 404 -> miss) and ``POST {base}/kv/{key}`` with a JSON body. A
    Redis/Postgres/Memcached gateway can implement this small surface; no
    hard dependency is added to charter. Falls back to a miss on any network
    error so the cache chain degrades gracefully (offline-safe / CI green).
    """

    def __init__(self, base_url: str, timeout_s: float = 2.0,
                 api_key: Optional[str] = None) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = float(timeout_s)
        self._api_key = api_key
        self._closed = False

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def get(self, key: str) -> Optional[Any]:
        if self._closed:
            return None
        import json as _json
        import urllib.request
        import urllib.error
        try:
            req = urllib.request.Request(
                f"{self._base}/kv/{urllib.parse.quote(str(key))}",
                headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                body = r.read()
            return _json.loads(body.decode("utf-8")) if body else None
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            return None  # offline-safe: miss, never crash the chain

    def put(self, key: str, value: Any) -> None:
        if self._closed:
            return
        import json as _json
        import urllib.request
        import urllib.error
        try:
            req = urllib.request.Request(
                f"{self._base}/kv/{urllib.parse.quote(str(key))}",
                data=_json.dumps(value).encode("utf-8"),
                headers=self._headers(), method="POST")
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                r.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            pass  # offline-safe: local layers already hold the value

    def close(self) -> None:
        self._closed = True

    def name(self) -> str:
        return f"http:{self._base}"


def make_remote_backend(kind: str, base_url: str = "",
                        api_key: Optional[str] = None,
                        timeout_s: float = 2.0) -> SemanticCacheBackend:
    """Factory for remote cache backends.

    ``kind``:
      - ``"http"`` / ``"kv"``  -> :class:`HTTPKeyValueBackend`
      - ``"null"``            -> no-op backend (explicitly disable remote)
    Unknown kinds raise ``ValueError``. The chosen backend is wired into
    ``SemanticCache(remote=...)`` as the L3 (remote) tier.
    """
    k = (kind or "").lower()
    if k in ("http", "kv", "redis", "postgres", "memcached"):
        # All network KV stores are reached through the same thin HTTP surface
        # (deploy a gateway that translates to the real store); keep one
        # stdlib implementation, offline-safe.
        return HTTPKeyValueBackend(base_url, timeout_s=timeout_s, api_key=api_key)
    if k in ("null", "none", ""):
        return _NullBackend()
    raise ValueError(f"unknown remote backend kind: {kind!r}")


class _NullBackend(SemanticCacheBackend):
    def get(self, key: str) -> Optional[Any]:
        return None

    def put(self, key: str, value: Any) -> None:
        pass

    def name(self) -> str:
        return "null"
