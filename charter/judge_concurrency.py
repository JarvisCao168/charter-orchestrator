"""Multi-provider judge concurrency + result cache (v2.6).

Lifts `charter/judge_voting.py` (sequential provider voting) to:

    1. **Concurrency** - `vote_judges_concurrent(...)` runs N provider
       judges on a thread pool (stdlib `concurrent.futures`) instead of one
       after another, so a 4-provider vote takes ~max(latency) not
       sum(latency). The result is the *same* weighted-voting aggregation
       as `vote_judges`, computed from the concurrently-collected votes.
    2. **Result cache** - a `JudgeResultCache` keyed by
       (artifact-fingerprint, backend-set, models, weights, threshold). A
       repeated vote for the same artifacts + config is O(1) instead of N
       LLM calls. The cache is LRU (in-memory) + optional SQLite disk, so
       hot eval loops don't re-burn tokens.

Stdlib-only. Offline-safe: with no live backends the concurrent vote falls
back to the heuristic judge exactly like `vote_judges` (mode=
"no-votes-fallback"), and the cache stores that fallback result too.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from .judge_voting import (
    ProviderVote, WeightedVotingJudge, vote_judges, accuracy_weights,
)
from .llm_judge_online import make_judge, _judge_prompt

__all__ = [
    "vote_judges_concurrent", "JudgeResultCache", "cached_vote",
]


def _artifact_fingerprint(artifacts: Dict[str, Any]) -> str:
    """Stable hash of the artifacts dict (order-insensitive where possible)."""
    blob = json.dumps(artifacts, sort_keys=True,
                      ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _cache_key(project_id: str, artifacts: Dict[str, Any],
               backends: List[str], models: Optional[List[str]],
               weights: Optional[Dict[str, float]],
               threshold: float) -> str:
    fp = _artifact_fingerprint(artifacts)
    cfg = json.dumps({
        "backends": sorted(backends or ["agnes", "openai"]),
        "models": models, "weights": weights, "threshold": threshold,
        "project": project_id,
    }, sort_keys=True, default=str)
    return f"{fp}|{hashlib.sha256(cfg.encode()).hexdigest()[:16]}"


class JudgeResultCache:
    """Two-level (LRU + optional SQLite) cache for vote results."""

    def __init__(self, lru_size: int = 512,
                 disk_path: Optional[str] = None) -> None:
        self.lru_size = lru_size
        self._mem: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self._db = None
        if disk_path:
            d = disk_path or os.environ.get(
                "JUDGE_CACHE_PATH",
                os.path.join(os.path.expanduser("~"), ".charter",
                             "judge_cache.db"))
            os.makedirs(os.path.dirname(d) or ".", exist_ok=True)
            self._db = sqlite3.connect(d, check_same_thread=False)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS judge_cache ("
                "cache_key TEXT PRIMARY KEY, result TEXT, hits INTEGER"
                " DEFAULT 0)")
            self._db.commit()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if key in self._mem:
                self._mem.move_to_end(key)
                return self._mem[key]
        if self._db:
            row = self._db.execute(
                "SELECT result FROM judge_cache WHERE cache_key=?",
                (key,)).fetchone()
            if row:
                self._db.execute(
                    "UPDATE judge_cache SET hits=hits+1 WHERE cache_key=?",
                    (key,))
                self._db.commit()
                result = json.loads(row[0])
                with self._lock:
                    self._mem[key] = result
                    self._mem.move_to_end(key)
                    while len(self._mem) > self.lru_size:
                        self._mem.popitem(last=False)
                return result
        return None

    def put(self, key: str, result: Dict[str, Any]) -> None:
        with self._lock:
            self._mem[key] = result
            self._mem.move_to_end(key)
            while len(self._mem) > self.lru_size:
                self._mem.popitem(last=False)
        if self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO judge_cache (cache_key, result)"
                " VALUES (?,?)", (key, json.dumps(result, default=str)))
            self._db.commit()

    def stats(self) -> Dict[str, Any]:
        return {"mem": len(self._mem), "cap": self.lru_size,
                "disk": self._db is not None}


def _run_one(backend: str, model: Optional[str], prompt: str,
             api_key: Optional[str]) -> Optional[ProviderVote]:
    """Collect one provider's vote (used on a worker thread)."""
    jb = make_judge(backend=backend, api_key=api_key, model=model)
    if type(jb).__name__ == "OfflineJudge":
        return None
    key = f"{jb.name}" + (f"-{jb.model}" if getattr(jb, "model", None) else "")
    try:
        raw = jb.judge(prompt)
        return ProviderVote(provider=key, scores=raw["scores"],
                           verdict=raw.get("verdict", "pass"))
    except Exception:
        return None


def vote_judges_concurrent(
        project_id: str, artifacts: Dict[str, Any],
        backends: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        threshold: float = 0.7,
        api_key: Optional[str] = None,
        max_workers: int = 4,
        timeout_s: int = 90) -> Dict[str, Any]:
    """tool: vote_judges_concurrent - concurrent multi-provider weighted vote.

    Same output shape as `vote_judges` (`weighted`/`passed`/`verdict`/
    `scores`/`details{mode, n_providers, contributions, effective_agreement,
    votes, excluded}`) but the provider judges run on a thread pool. When
    `max_workers` >= len(backends) the N providers run in parallel; the
    aggregation is identical to the sequential path.
    """
    backends = backends or ["agnes", "openai"]
    prompt = _judge_prompt(artifacts)

    collected: List[Optional[ProviderVote]] = [None] * len(backends)
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers,
                                                    len(backends)))) as pool:
        futs = {
            pool.submit(_run_one, backends[i],
                       (models[i] if models and i < len(models) else None),
                       prompt, api_key): i
            for i in range(len(backends))
        }
        for fut, i in futs.items():
            try:
                collected[i] = fut.result(timeout=timeout_s)
            except Exception:
                collected[i] = None

    votes = [v for v in collected if v is not None]
    judge = WeightedVotingJudge(threshold=threshold)
    if weights:
        judge.set_weights(weights)
    result = judge.aggregate(votes)
    result["project_id"] = project_id
    result["details"]["mode"] = ("concurrent-" + result["details"]["mode"]
                                 if result["details"]["mode"] !=
                                 "no-votes-fallback" else
                                 result["details"]["mode"])
    result["details"]["concurrent"] = True
    result["details"]["max_workers"] = max_workers
    result["details"]["excluded"] = [
        b for b, v in zip(backends, collected) if v is None]
    return result


def cached_vote(
        project_id: str, artifacts: Dict[str, Any],
        backends: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        threshold: float = 0.7,
        api_key: Optional[str] = None,
        cache: Optional[JudgeResultCache] = None,
        concurrent: bool = True,
        max_workers: int = 4) -> Dict[str, Any]:
    """tool: cached_vote - vote_judges with a transparent result cache.

    Repeated calls with the same (artifacts, config) hit the cache instead
    of re-running N providers. `details["cache_hit"]` is True when the
    result came from the cache.
    """
    backends = backends or ["agnes", "openai"]
    cache = cache or JudgeResultCache()
    key = _cache_key(project_id, artifacts, backends, models, weights,
                     threshold)
    hit = cache.get(key)
    if hit is not None:
        out = dict(hit)
        out["details"] = dict(out.get("details", {}))
        out["details"]["cache_hit"] = True
        out["details"]["cache"] = cache.stats()
        return out
    out = (vote_judges_concurrent(project_id, artifacts, backends=backends,
                                  models=models, weights=weights,
                                  threshold=threshold, api_key=api_key,
                                  max_workers=max_workers)
           if concurrent
           else vote_judges(project_id, artifacts, backends=backends,
                            models=models, weights=weights,
                            threshold=threshold, api_key=api_key))
    cache.put(key, out)
    out = dict(out)
    out["details"] = dict(out.get("details", {}))
    out["details"]["cache_hit"] = False
    out["details"]["cache"] = cache.stats()
    return out
