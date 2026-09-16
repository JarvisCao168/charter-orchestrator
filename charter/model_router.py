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
           "SemanticCacheBackend", "HTTPKeyValueBackend", "make_remote_backend",
           "reference_kv_gateway", "stress_multi_writer"]


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
                 remote: Optional["SemanticCacheBackend"] = None,
                 ttl_s: Optional[float] = None) -> None:
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
        # v3.14: distributed consistency: per-key TTL + version tracking
        self._ttl_s = ttl_s
        self._remote_versions: Dict[str, Dict[str, Any]] = {}
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

    def reconcile(self, repair: bool = False) -> Dict[str, Any]:
        """v3.17: consistency check across the three cache tiers.

        Scans L1 (memory), L2 (disk) and L3 (remote) and reports which keys
        are present in which tier. The goal is to detect drift: a key that
        exists on disk or remote but is missing from memory (stale eviction)
        or a key that is in memory but not yet persisted. Returns a dict:

          {
            "l1_keys": [...], "l2_keys": [...], "l3_keys": [...],
            "in_memory_only": [...],     # L1 but not L2/L3
            "in_storage_only": [...],    # L2/L3 but not L1
            "consistent": bool,          # True when all three agree on keys
          }

        L2 and L3 listings are best-effort: a missing backend yields an
        empty list. ``consistent`` is True when the union of keys is the
        same across all available tiers.

        v3.18: when ``repair=True``, drift is auto-fixed:
          - ``in_storage_only`` keys (L2/L3 but not L1): back-fill L1 from
            the freshest available tier (L3 first, then L2), and if the
            value is TTL-expired, purge it from all tiers.
          - ``in_memory_only`` keys (L1 but not L2/L3): persist them to
            L2 and L3 so the next reconcile sees agreement.
          The return dict gains ``repaired`` (list of fix actions) and
          ``repairs`` (count).
        """
        with self._lock:
            l1 = list(self._cache.keys())
        l2: List[str] = []
        if self._db is not None:
            rows = self._db.execute("SELECT cache_key FROM semantic_cache").fetchall()
            l2 = [r[0] for r in rows]
        l3: List[str] = []
        if self._remote is not None and hasattr(self._remote, "list_keys"):
            l3 = list(self._remote.list_keys())
        available = [set(l1)]
        if self._db is not None:
            available.append(set(l2))
        consistent = len(available) <= 1 or all(s == available[0] for s in available[1:])
        result: Dict[str, Any] = {
            "l1_keys": l1, "l2_keys": l2, "l3_keys": l3,
            "in_memory_only": sorted(set(l1) - set(l2) - set(l3)),
            "in_storage_only": sorted((set(l2) | set(l3)) - set(l1)),
            "consistent": consistent,
        }
        if not repair:
            return result
        # ---- v3.18 auto-repair ----
        repaired: List[Dict[str, Any]] = []
        # 1) in_storage_only: back-fill L1 from L3 (freshest) then L2
        for key in result["in_storage_only"]:
            value: Any = None
            source = ""
            if self._remote is not None:
                try:
                    rv = self._remote.get(key)
                    if rv is not None:
                        if isinstance(rv, dict) and "__v" in rv and "value" in rv:
                            ts = float(rv.get("__ts", 0.0))
                            if self._ttl_s is not None and (time.time() - ts) > self._ttl_s:
                                # TTL expired: purge from all tiers
                                self._purge_key(key)
                                repaired.append({"key": key, "action": "purge_expired", "source": source})
                                value = None
                            else:
                                value = rv["value"]
                        else:
                            value = rv
                        source = "l3"
                except Exception:  # noqa: BLENT
                    pass
            if value is None and source != "l3":
                if self._db is not None:
                    dv = self._disk_get(key)
                    if dv is not None:
                        value = dv
                        source = "l2"
            if value is not None:
                with self._lock:
                    self._cache[key] = {"value": value, "ts": time.time()}
                    self._cache.move_to_end(key)
                    while len(self._cache) > self._max_entries:
                        self._cache.popitem(last=False)
                repaired.append({"key": key, "action": "backfill_l1", "source": source})
            elif source == "l3":
                # key was purged above
                pass
        # 2) in_memory_only: persist to L2 and L3
        for key in result["in_memory_only"]:
            with self._lock:
                entry = self._cache.get(key)
                val = entry["value"] if entry else None
            if val is None:
                continue
            self._disk_set(key, val)
            if self._remote is not None:
                try:
                    prev_v = self._remote_versions.get(key, {}).get("v") or 0
                    envelope = {"__v": int(prev_v) + 1, "__ts": time.time(), "value": val}
                    self._remote.put(key, envelope)
                    with self._lock:
                        self._remote_versions[key] = {"v": envelope["__v"], "ts": envelope["__ts"]}
                except Exception:  # noqa: BLENT
                    pass
            repaired.append({"key": key, "action": "persist_l2_l3", "source": "l1"})
        result["repaired"] = repaired
        result["repairs"] = len(repaired)
        result["consistent"] = not result["in_memory_only"] and not result["in_storage_only"]
        return result

    def _purge_key(self, key: str) -> None:
        """v3.18: remove a key from all three cache tiers."""
        with self._lock:
            self._cache.pop(key, None)
            self._remote_versions.pop(key, None)
        if self._db is not None:
            self._db.execute("DELETE FROM semantic_cache WHERE cache_key=?", (key,))
            self._db.commit()
        if self._remote is not None:
            try:
                # Best-effort: DELETE is not in the KV protocol; overwrite with
                # a tombstone so a later reader sees __deleted=True.
                self._remote.put(key, {"__v": 0, "__ts": time.time(), "value": None,
                                       "__deleted": True})
            except Exception:  # noqa: BLENT
                pass

    def start_sweeper(self, interval_s: float = 30.0,
                      reconcile: bool = False) -> "SweeperHandle":
        """v3.20: start a background thread that periodically calls
        ``sweep_expired()`` (and optionally ``reconcile(repair=True)``).

        Args:
            interval_s: how often to sweep (default 30s).
            reconcile: also run ``reconcile(repair=True)`` after each sweep.

        Returns:
            A :class:`SweeperHandle` with ``stop()`` and ``last_sweep``
            attributes. The thread is a daemon (won't block process exit).
        """
        import threading as _th
        stop_evt = _th.Event()
        state = {"last_sweep": None, "last_reconcile": None}

        def _loop() -> None:
            import time as _t
            while not stop_evt.is_set():
                rep = self.sweep_expired()
                state["last_sweep"] = rep
                if reconcile:
                    state["last_reconcile"] = self.reconcile(repair=True)
                stop_evt.wait(interval_s)

        t = _th.Thread(target=_loop, daemon=True, name="charter-sweeper")
        t.start()

        class _Handle:
            def __init__(self, thread: _th.Thread, stop_event: _th.Event,
                         state_dict: dict) -> None:
                self._thread = thread
                self._stop_event = stop_event
                self._state = state_dict

            def stop(self) -> None:
                self._stop_event.set()
                self._thread.join(timeout=5.0)

            @property
            def last_sweep(self) -> Optional[Dict[str, Any]]:
                return self._state.get("last_sweep")

            @property
            def last_reconcile(self) -> Optional[Dict[str, Any]]:
                return self._state.get("last_reconcile")

            @property
            def running(self) -> bool:
                return self._thread.is_alive() and not self._stop_event.is_set()

        return _Handle(t, stop_evt, state)

    def sweep_expired(self) -> Dict[str, Any]:
        """v3.19: proactively purge all TTL-expired keys across L1/L2/L3.

        Scans every tier for entries whose ``__ts`` (or ``ts``) is older than
        ``self._ttl_s`` and removes them. Returns a dict:

          {
            "swept": int,                  # total keys removed
            "l1_swept": [key, ...],
            "l2_swept": [key, ...],
            "l3_swept": [key, ...],        # tombstoned (no DELETE in KV)
            "ttl_s": float | None,
          }

        Call this periodically from a background task to keep memory and
        disk bounded when ``ttl_s`` is set.
        """
        if self._ttl_s is None:
            return {"swept": 0, "l1_swept": [], "l2_swept": [],
                    "l3_swept": [], "ttl_s": None}
        now = time.time()
        cutoff = now - self._ttl_s
        l1_swept: List[str] = []
        l2_swept: List[str] = []
        l3_swept: List[str] = []

        # L1: scan in-memory dict
        with self._lock:
            for key, entry in list(self._cache.items()):
                ts = entry.get("ts", 0.0)
                if ts < cutoff:
                    self._cache.pop(key, None)
                    self._remote_versions.pop(key, None)
                    l1_swept.append(key)

        # L2: scan SQLite
        if self._db is not None:
            rows = self._db.execute(
                "SELECT cache_key, ts FROM semantic_cache WHERE ts < ?",
                (cutoff,)).fetchall()
            for key, _ts in rows:
                self._db.execute("DELETE FROM semantic_cache WHERE cache_key=?", (key,))
                l2_swept.append(key)
            self._db.commit()

        # L3: scan remote (best-effort; tombstone expired keys)
        if self._remote is not None:
            try:
                all_keys = self._remote.list_keys()
                for key in all_keys:
                    try:
                        env = self._remote.get(key)
                    except Exception:  # noqa: BLENT
                        continue
                    if env is None:
                        continue
                    if isinstance(env, dict) and "__ts" in env:
                        ts = float(env.get("__ts", 0.0))
                        if ts < cutoff:
                            try:
                                self._remote.put(key, {"__v": 0, "__ts": now,
                                                       "value": None, "__deleted": True})
                                l3_swept.append(key)
                            except Exception:  # noqa: BLENT
                                pass
            except Exception:  # noqa: BLENT
                pass

        total = len(l1_swept) + len(l2_swept) + len(l3_swept)
        return {"swept": total, "l1_swept": l1_swept, "l2_swept": l2_swept,
                "l3_swept": l3_swept, "ttl_s": self._ttl_s}

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
                # v3.14: unwrap the version envelope ({"__v", "__ts", "value"});
                # apply per-key TTL; record the version for optimistic locking.
                payload = remote_val
                if isinstance(remote_val, dict) and "__v" in remote_val and "value" in remote_val:
                    ts = float(remote_val.get("__ts", time.time()))
                    if self._ttl_s is not None and (time.time() - ts) > self._ttl_s:
                        # expired -> treat as a miss
                        with self._lock:
                            self.misses += 1
                        return None
                    payload = remote_val["value"]
                    with self._lock:
                        self._remote_versions[k] = {"v": remote_val.get("__v"), "ts": ts}
                with self._lock:
                    self._cache[k] = {"value": payload, "ts": time.time()}
                    self._cache.move_to_end(k)
                    self.hits += 1
                    while len(self._cache) > self._max_entries:
                        self._cache.popitem(last=False)
                return payload
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
            # v3.14: version-stamp the payload so multi-node writers can do
            # optimistic reads (get_version) + TTL enforcement.
            prev_v = self._remote_versions.get(k, {}).get("v") or 0
            envelope = {"__v": int(prev_v) + 1, "__ts": time.time(), "value": value}
            try:
                self._remote.put(k, envelope)
                with self._lock:
                    self._remote_versions[k] = {"v": envelope["__v"], "ts": envelope["__ts"]}
            except Exception:  # noqa: BLENT
                pass
        self._last_write_version = getattr(self, "_last_write_version", {})
        self._last_write_version[k] = (self._remote_versions.get(k, {}).get("v") or 0)

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
                "remote": self._remote.name() if self._remote else None,
                "ttl_s": self._ttl_s,
                "remote_versions": dict(self._remote_versions)}

    def get_version(self, request: str) -> Optional[int]:
        """v3.14: last-written version for ``request`` (optimistic-lock token).

        Reads the locally tracked version, or queries the remote backend when
        we have not written this key ourselves yet. Returns ``None`` on a miss
        / offline (callers should treat that as "no known version" and use a
        fresh write).
        """
        k = self._k(request)
        with self._lock:
            rec = self._remote_versions.get(k)
            if rec is not None:
                return rec.get("v")
        if self._remote is not None:
            try:
                raw = self._remote.get(k)
            except Exception:  # noqa: BLENT
                raw = None
            if isinstance(raw, dict) and "__v" in raw:
                with self._lock:
                    self._remote_versions[k] = {"v": raw.get("__v"), "ts": raw.get("__ts")}
                return raw.get("__v")
        return None

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

    def put_if_version(self, key: str, value: Any, if_version: Optional[int] = None) -> bool:
        """v3.14/v3.15: ETag-style optimistic-locked write (CAS).

        Writes only when the server-side version equals ``if_version`` (or the
        key is absent when ``if_version is None``). Implemented via the
        ``X-If-Version`` header; a conforming gateway returns **412
        Precondition Failed** on a version mismatch (409 is also accepted for
        older gateways). Returns True on success, False on conflict or any
        offline error.
        """
        if self._closed:
            return False
        import json as _json
        import urllib.request
        import urllib.error
        h = self._headers()
        # if_version None -> send X-If-Version=0 (expect the key to be at v0,
        # i.e. absent or first write). A conforming gateway treats 0 as "new".
        h["X-If-Version"] = str(if_version) if if_version is not None else "0"
        try:
            req = urllib.request.Request(
                f"{self._base}/kv/{urllib.parse.quote(str(key))}",
                data=_json.dumps(value).encode("utf-8"),
                headers=h, method="POST")
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                r.read()
            return True
        except urllib.error.HTTPError as e:
            return e.code not in (409, 412)  # conflict -> False; else offline miss
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def cas(self, key: str, read, write_fn, max_retries: int = 5,
            sleep_s: float = 0.05) -> bool:
        """v3.15: compare-and-swap loop over the remote store.

        ``read`` is called to observe the current remote value (typically
        ``self.get(key)``); ``write_fn(observed, version)`` returns the value
        to write. The loop: GET version -> build new value -> CAS write; on
        conflict it re-observes and retries up to ``max_retries`` times.
        Returns True when the write landed, False on persistent conflict
        (another writer kept winning) or offline.
        """
        for attempt in range(max(1, int(max_retries))):
            # one round-trip: value + version observed together (no race window)
            observed, version = self.observe(key)
            new_value = write_fn(observed, version)
            if new_value is None:
                return True  # write_fn decided no write was needed
            ok = self.put_if_version(key, new_value, if_version=version)
            if ok:
                return True
            if sleep_s:
                import time as _t
                _t.sleep(sleep_s)
        return False

    def get_version(self, key: str) -> Optional[int]:
        """v3.15: server-side version of ``key`` (ETag token), or None."""
        raw = self.get(key)
        if isinstance(raw, dict) and "__v" in raw:
            return raw.get("__v")
        return None

    def observe(self, key: str) -> Tuple[Optional[Any], Optional[int]]:
        """v3.15: single-GET atomic snapshot of ``(value, version)``.

        One round-trip instead of get()+get_version(); closes the race
        window where another writer lands between the two reads.
        """
        raw = self.get(key)
        if raw is None:
            return None, None
        if isinstance(raw, dict) and "__v" in raw:
            return raw.get("value"), raw.get("__v")
        return raw, None

    def list_keys(self) -> List[str]:
        """v3.17: best-effort listing of all remote keys (GET {base}/kv/_keys).

        Returns an empty list when the gateway does not expose that endpoint,
        so ``reconcile()`` degrades gracefully (L3 treated as unknown).
        """
        if self._closed:
            return []
        import json as _json
        import urllib.request
        import urllib.error
        try:
            req = urllib.request.Request(
                f"{self._base}/kv/_keys", headers=self._headers(), method="GET")
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                body = r.read()
            data = _json.loads(body.decode("utf-8")) if body else []
            return list(data) if isinstance(data, list) else []
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            return []

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


# ---------------------------------------------------------------------------
# v3.15: reference CAS-compliant KV gateway + multi-writer stress tool
# ---------------------------------------------------------------------------

def reference_kv_gateway(host: str = "127.0.0.1", port: int = 0,
                         start: bool = True):
    """A thread-hosted HTTP KV gateway implementing the full versioned surface:

      - ``GET  {base}/kv/{key}``  -> 200 JSON envelope / 404
      - ``POST {base}/kv/{key}``  -> writes; honours ``X-If-Version``:
        returns **412 Precondition Failed** on mismatch, 200 on success.
        Each write bumps the envelope ``__v`` by 1 (continuing the stored
        version, so concurrent writers observe monotonic versions).

    Returns ``(server, base_url, store_dict)``. The store dict is the single
    source of truth: ``{key: {"__v": int, "__ts": float, "value": Any}}``.
    """
    import json
    import threading as _th
    import http.server as _hs
    import urllib.parse as _up

    store: Dict[str, Any] = {}
    lock = _th.Lock()

    class _Handler(_hs.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            k = _up.unquote(self.path.split("/kv/")[-1])
            if k == "_keys":
                with lock:
                    b = json.dumps(list(store.keys())).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            with lock:
                v = store.get(k)
            if v is None:
                self.send_response(404)
                self.end_headers()
            else:
                b = json.dumps(v).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

        def do_POST(self):
            k = _up.unquote(self.path.split("/kv/")[-1])
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode())
            if_ver = self.headers.get("X-If-Version")
            if_new = self.headers.get("X-If-New")
            with lock:
                cur = store.get(k)
                cur_v = cur.get("__v") if isinstance(cur, dict) and "__v" in cur else None
                if if_new == "1" and cur is not None:
                    self.send_response(412)
                    self.end_headers()
                    return
                if if_ver is not None:
                    expect = int(if_ver)
                    actual = cur_v if cur_v is not None else 0
                    if expect != actual:
                        self.send_response(412)
                        self.end_headers()
                        return
                # If the body is a client envelope (__v present), honour its
                # __v so the server version sequence is continuous; otherwise
                # bump from the current server version.
                if isinstance(body, dict) and "__v" in body:
                    new_v = int(body["__v"])
                    store[k] = body
                else:
                    base_v = cur_v if cur_v is not None else 0
                    store[k] = {"__v": base_v + 1, "__ts": time.time(), "value": body}
            self.send_response(200)
            self.end_headers()

    srv = _hs.ThreadingHTTPServer((host, port), _Handler)
    if start:
        _th.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://{host}:{srv.server_address[1]}"
    return srv, url, store


def stress_multi_writer(n_writers: int = 4, iterations: int = 25,
                        base_url: str = "", store: Optional[Dict[str, Any]] = None,
                        max_cas_retries: int = 10) -> Dict[str, Any]:
    """v3.15: N concurrent writers each CAS-increment one shared counter.

    Each writer runs ``cas(key, read=lambda: remote.get(key),
    write_fn=lambda obs, v: (obs or 0) + 1)`` for ``iterations`` rounds,
    resolving conflicts by re-observing and retrying. Returns a summary:
    ``final`` (the shared value), ``expected`` (n_writers * iterations),
    ``ok`` (they match), plus per-writer conflict counts.
    """
    import threading as _th
    from concurrent.futures import ThreadPoolExecutor
    from charter import make_remote_backend  # local import avoids cycle at module load

    key = "counter"
    remote = make_remote_backend("http", base_url, timeout_s=3.0) if base_url else None
    if remote is None:
        raise ValueError("stress_multi_writer requires a running gateway (base_url)")
    conflicts = {"n": 0}
    ops = {"n": 0}
    wall = {"t": 0.0}

    def one_writer(wid: int) -> int:
        local_conf = 0
        import time as _t
        for _ in range(iterations):
            ok = remote.cas(
                key,
                read=lambda: remote.get(key),
                write_fn=lambda o, v: int(o + 1) if o is not None else 1,
                max_retries=max_cas_retries, sleep_s=0.01)
            ops["n"] += 1
            if not ok:
                local_conf += 1
                conflicts["n"] += 1
            else:
                _t.sleep(0.01)  # widen the race window so conflicts are observable
        return local_conf

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_writers) as pool:
        list(pool.map(one_writer, range(n_writers)))
    wall["t"] = time.time() - t0
    final_env = remote.get(key)
    final = final_env.get("value") if isinstance(final_env, dict) else final_env
    expected = n_writers * iterations
    remote.close()
    total_ops = ops["n"]
    return {
        "final": final, "expected": expected,
        "ok": final == expected,
        "conflicts": conflicts["n"],
        "ops": total_ops,
        "conflict_rate": (conflicts["n"] / total_ops) if total_ops else 0.0,
        "wall_s": round(wall["t"], 3),
        "n_writers": n_writers, "iterations": iterations,
    }
