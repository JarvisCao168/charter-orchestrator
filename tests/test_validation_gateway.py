"""Tests for charter/validation_gateway (v3.11 three-layer gate + breaker)."""
from __future__ import annotations

import time

import charter.validation_gateway as vg


# ---------------------------------------------------------------------------
# Layer 1 - contract
# ---------------------------------------------------------------------------

def test_contract_missing_required():
    violations = vg.check_contract({"a": 1}, {"a": {"type": "int"}, "b": {"type": "str", "required": True}})
    assert any(v["kind"] == "missing_required" and v["field"] == "b" for v in violations)


def test_contract_type_mismatch():
    violations = vg.check_contract({"a": "not-an-int"}, {"a": {"type": "int"}})
    assert any(v["kind"] == "type_mismatch" for v in violations)


def test_contract_bool_not_int():
    # bool is a subclass of int in Python; schema int must reject bool.
    violations = vg.check_contract({"a": True}, {"a": {"type": "int"}})
    assert any(v["kind"] == "type_mismatch" for v in violations)


def test_contract_valid():
    assert vg.check_contract({"a": 1, "s": "x"},
                            {"a": {"type": "int"}, "s": {"type": "str"}}) == []


# ---------------------------------------------------------------------------
# Layer 2 - data alignment
# ---------------------------------------------------------------------------

def test_data_alignment_detects_drift():
    rec = vg.check_data_alignment(
        {"market_size": 1200e9}, {"market_size": 500e9},
        key="market_size", rel_tol=0.10)
    assert rec is not None and rec["kind"] == "data_drift"
    assert rec["rel_diff"] > 0.10


def test_data_alignment_within_tolerance():
    rec = vg.check_data_alignment(
        {"market_size": 520e9}, {"market_size": 500e9},
        key="market_size", rel_tol=0.10)
    assert rec is None


def test_data_alignment_non_numeric_mismatch():
    rec = vg.check_data_alignment(
        {"region": "EMEA"}, {"region": "APAC"}, key="region")
    assert rec is not None and rec["kind"] == "value_mismatch"


# ---------------------------------------------------------------------------
# Layer 3 - consistency
# ---------------------------------------------------------------------------

def test_consistency_detects_contradiction():
    rec = vg.check_consistency(
        {"q2": "growth"}, {"q1": "decline"},
        facts={"q2": "q1"})
    assert rec is not None and rec["kind"] == "contradiction"


def test_consistency_agreement_passes():
    rec = vg.check_consistency({"q2": "growth"}, {"q1": "growth"},
                               facts={"q2": "q1"})
    assert rec is None


# ---------------------------------------------------------------------------
# Aggregate layered_check
# ---------------------------------------------------------------------------

def test_layered_check_all_pass():
    v = vg.layered_check(
        {"a": 1, "b": "x"}, {"a": {"type": "int"}, "b": {"type": "str"}},
        upstream={"a": 1}, alignment_key="a")
    assert v.passed is True
    assert v.failed_layers() == []


def test_layered_check_multi_layer_failure():
    v = vg.layered_check(
        {"a": 999},  # not a real int violation; a is present but let's make it drift
        {"a": {"type": "int", "required": True}},
        upstream={"a": 1}, alignment_key="a")
    assert v.passed is False
    assert 1 in v.failed_layers()


# ---------------------------------------------------------------------------
# ValidationGateway retry + degrade
# ---------------------------------------------------------------------------

def test_gateway_pass_first_try():
    gw = vg.ValidationGateway({"a": {"type": "int"}})
    out = gw.check_with_retry(lambda: {"a": 5})
    assert out["_gw"]["passed"] is True
    assert out["_gw"]["attempts"] == 1


def test_gateway_degrades_after_retries():
    gw = vg.ValidationGateway({"a": {"type": "int", "required": True, "default": 0}})
    # producer always returns a missing-required field -> never passes
    out = gw.check_with_retry(lambda: {"b": 1})
    assert out["_gw"]["degraded"] is True
    assert out["_gw"]["attempts"] == gw.max_local_retries + 1
    # default was filled
    assert out["a"] == 0
    assert len(gw.incidents) == 1


def test_gateway_degrade_fn_hook():
    def degrade(out, verdict):
        return {"a": 42}
    gw = vg.ValidationGateway({"a": {"type": "int", "required": True}},
                              degrade_fn=degrade)
    out = gw.check_with_retry(lambda: {})
    assert out["a"] == 42
    assert out["_gw"]["degraded"] is True


def test_gateway_stats():
    gw = vg.ValidationGateway({"a": {"type": "int"}})
    gw.check({"a": 1})
    gw.check({"b": 2})
    s = gw.stats()
    assert s["checks"] == 2
    assert s["incidents"] == 0  # plain check() does not record incidents


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

def test_breaker_opens_after_threshold():
    brk = vg.CircuitBreaker(failure_threshold=2, cooldown_s=0.05, now_fn=time.time)
    assert brk.state_snapshot() == "closed"
    brk.record_failure()
    assert brk.state_snapshot() == "closed"
    brk.record_failure()
    assert brk.state_snapshot() == "open"
    assert brk.allow() is False


def test_breaker_half_opens_after_cooldown():
    t = [0.0]
    def fake_now():
        return t[0]
    brk = vg.CircuitBreaker(failure_threshold=1, cooldown_s=10.0, now_fn=fake_now)
    brk.record_failure()
    assert brk.state_snapshot() == "open"
    t[0] = 5.0  # within cooldown
    assert brk.state_snapshot() == "open"
    t[0] = 11.0  # past cooldown -> half-open
    assert brk.state_snapshot() == "half_open"
    assert brk.allow() is True


def test_breaker_closes_on_probe_success():
    brk = vg.CircuitBreaker(failure_threshold=1, cooldown_s=0.0, now_fn=lambda: 9999.0)
    brk.record_failure()
    assert brk.state_snapshot() == "half_open"
    brk.record_success()
    assert brk.state_snapshot() == "closed"


def test_with_breaker_short_circuits_open():
    t = [0.0]
    brk = vg.CircuitBreaker(failure_threshold=1, cooldown_s=100.0, now_fn=lambda: t[0])
    brk.record_failure()  # now open (cooldown 100s, only 0s elapsed)
    assert brk.state_snapshot() == "open"
    assert brk.allow() is False
    receipt = vg.with_breaker(brk, lambda: "should not run")
    assert receipt["ok"] is False
    assert receipt["error"] == "circuit open"


def test_with_breaker_success_closes():
    brk = vg.CircuitBreaker(failure_threshold=3, cooldown_s=0.0, now_fn=lambda: 1.0)
    receipt = vg.with_breaker(brk, lambda: 7)
    assert receipt["ok"] is True and receipt["result"] == 7
    assert receipt["breaker"]["state"] == "closed"


def test_gateway_guard_uses_breaker():
    t = [0.0]
    brk = vg.CircuitBreaker(failure_threshold=1, cooldown_s=100.0, now_fn=lambda: t[0])
    gw = vg.ValidationGateway({"a": {"type": "int"}})
    r = gw.guard("tool_x", lambda: 3, breaker=brk)
    assert r["ok"] is True and r["result"] == 3
    brk.record_failure()  # force open
    assert brk.state_snapshot() == "open"
    r2 = gw.guard("tool_x", lambda: 3, breaker=brk)
    assert r2["ok"] is False and r2["error"] == "circuit open"
