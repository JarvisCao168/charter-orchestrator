"""Tests for charter/model_router (v3.11 tier routing + semantic cache)."""
from __future__ import annotations

import charter.model_router as mr


# ---------------------------------------------------------------------------
# TaskProfile complexity
# ---------------------------------------------------------------------------

def test_task_profile_low_complexity():
    p = mr.TaskProfile(depth=1, fan_in=1, risk=0.0, tokens=100)
    assert p.complexity() < 20.0


def test_task_profile_high_complexity():
    p = mr.TaskProfile(depth=10, fan_in=5, risk=1.0, tokens=4096,
                       requires_reasoning=True)
    assert p.complexity() >= 90.0


def test_task_profile_bounded_to_100():
    p = mr.TaskProfile(depth=100, fan_in=100, risk=1.0, tokens=10**9,
                       requires_reasoning=True)
    assert p.complexity() == 100.0


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_route_easy_goes_to_small():
    p = mr.TaskProfile(depth=1, fan_in=1, risk=0.1, tokens=200)
    r = mr.route_task(p)
    assert r["tier"] == "small"
    assert r["cost"] == 1.0


def test_route_hard_goes_to_large():
    p = mr.TaskProfile(depth=10, fan_in=5, risk=0.9, tokens=4096,
                       requires_reasoning=True)
    r = mr.route_task(p)
    assert r["tier"] == "large"
    assert r["cost"] == 10.0


def test_route_never_downgrades_below_min_complexity():
    """A complex task is not routed to a tier whose min_complexity exceeds it."""
    router = mr.ModelRouter()
    p = mr.TaskProfile(depth=1, fan_in=1, risk=0.1, tokens=200)  # low complexity
    tier = router.cheapest_qualified(p)
    # the cheapest qualifying tier for a low-complexity task is "small"
    assert tier.name == "small"


def test_route_custom_tiers():
    tiers = [
        mr.ModelTier("t0", "tiny", cost=0.5, min_complexity=0.0),
        mr.ModelTier("t1", "giant", cost=50.0, min_complexity=50.0),
    ]
    p = mr.TaskProfile(depth=2, fan_in=2, risk=0.2, tokens=500)
    r = mr.route_task(p, tiers)
    assert r["tier"] in ("t0", "t1")
    # complexity of this task: depth2*4=8 + fan_in2*4=8 + risk0.2*30=6
    # + tokens500/4096*10~1.2 = ~23.2, which is < 50, so t0 qualifies
    assert r["tier"] == "t0"


def test_route_reasoning_bumps_tier():
    base = mr.TaskProfile(depth=3, fan_in=2, risk=0.3, tokens=800)
    with_reasoning = mr.TaskProfile(depth=3, fan_in=2, risk=0.3, tokens=800,
                                    requires_reasoning=True)
    r_base = mr.route_task(base)
    r_with = mr.route_task(with_reasoning)
    assert with_reasoning.complexity() > base.complexity()
    # the reasoning variant must never route to a weaker tier
    tier_order = {t.name: i for i, t in enumerate(mr.ModelRouter().tiers)}
    assert tier_order[r_with["tier"]] >= tier_order[r_base["tier"]]


# ---------------------------------------------------------------------------
# Semantic cache
# ---------------------------------------------------------------------------

def test_cache_hit_on_identical_request():
    c = mr.SemanticCache()
    c.put("Q1 market size", 500)
    assert c.get("Q1 market size") == 500
    assert c.stats()["hits"] == 1


def test_cache_hit_on_normalized_request():
    """Whitespace / case differences still hit (default semantic key normalizes)."""
    c = mr.SemanticCache()
    c.put("  Q1   MARKET  SIZE ", 500)
    assert c.get("q1 market size") == 500


def test_cache_miss_on_different_request():
    c = mr.SemanticCache()
    c.put("Q1 market size", 500)
    assert c.get("Q2 market size") is None
    assert c.stats()["misses"] == 1


def test_cache_lru_eviction():
    c = mr.SemanticCache(max_entries=2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)  # evicts "a"
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3
    assert c.stats()["entries"] == 2


def test_cache_custom_semantic_key():
    # a key function that buckets by length (deterministic, test-friendly)
    def key(req: str) -> str:
        return f"len-{len(req)}"
    c = mr.SemanticCache(semantic_key=key)
    c.put("abc", 1)
    assert c.get("xyz") == 1  # same length -> same bucket
    assert c.get("abcdef") is None


def test_cache_stats_hit_rate():
    c = mr.SemanticCache()
    c.put("k", 1)
    c.get("k")   # hit
    c.get("k")   # hit
    c.get("other")  # miss
    s = c.stats()
    assert s["hits"] == 2 and s["misses"] == 1
    assert abs(s["hit_rate"] - 2 / 3) < 1e-9
