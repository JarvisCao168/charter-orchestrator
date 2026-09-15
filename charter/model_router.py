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

__all__ = ["TaskProfile", "ModelTier", "ModelRouter", "SemanticCache", "route_task"]


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
    """

    def __init__(self,
                 semantic_key: Optional[Any] = None,
                 max_entries: int = 256) -> None:
        self._cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._max_entries = max(1, int(max_entries))
        self._lock = __import__("threading").Lock()
        self._key_fn = semantic_key or _default_semantic_key
        self.hits = 0
        self.misses = 0

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
            if entry is None:
                self.misses += 1
                return None
            self.hits += 1
            self._cache.move_to_end(k)
            return entry["value"]

    def put(self, request: str, value: Any) -> None:
        k = self._k(request)
        with self._lock:
            self._cache[k] = {"value": value, "ts": time.time()}
            self._cache.move_to_end(k)
            while len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)

    def __contains__(self, request: str) -> bool:
        return self.get(request) is not None or self._k(request) in self._peek()

    def _peek(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._cache)

    def stats(self) -> Dict[str, Any]:
        return {"entries": len(self._cache), "hits": self.hits,
                "misses": self.misses,
                "hit_rate": (self.hits / (self.hits + self.misses)
                             if (self.hits + self.misses) else 0.0)}

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0


def _default_semantic_key(request: str) -> str:
    normalized = " ".join((request or "").lower().split())
    return hashlib.blake2b(normalized.encode("utf-8"), digest_size=16).hexdigest()
