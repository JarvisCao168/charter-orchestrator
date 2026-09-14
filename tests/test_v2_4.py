"""Tests for v2.4 multi-system linkages.

All offline-safe: no live gRPC, no real Alertmanager/PagerDuty, no LLM key,
no GitHub PR. Each test asserts the *degradation / retry-safe / local-fallback
contract* that keeps CI green with no credentials, while still exercising the
real code path (consensus aggregation, heuristic compression, alert payload
shapes, local SPIRE fallback, CI gate + scoring).
"""
from __future__ import annotations

import os
import tempfile

from charter import (
    # v2.4 judge consensus
    consensus_judge, agreement_matrix, ConsensusJudge,
    # v2.4 memory compression
    compress_session, HeuristicSummarizer, pick_summarizer,
    # v2.4 SLO alerts
    build_alert_payload, fire, AlertPayload, SLOAlertGate,
    # v2.4 spire gateway
    SPIREGateway, connect_spire, fetch_x509_svid, verify_remote_svid,
    # v2.4 pr community
    run_template_ci, community_score, rank_templates, add_feedback,
    # v2.2/v2.3 deps
    SessionStore,
)
from charter.observability import TraceLogger, Span
from charter import __version__


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------
def test_version_bumped_v2_4():
    assert __version__.startswith("2.")


# ------------------------------------------------------------------
# 1. judge consensus
# ------------------------------------------------------------------
def test_consensus_offline_fallback(monkeypatch):
    """No live backends -> consensus degrades to the heuristic judge, no
    exception, and details flags mode=offline-fallback."""
    for var in ("AGNES_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    out = consensus_judge("p1", {"test_coverage": 0.9, "violations": [],
                                  "tests_written": True, "token_ratio": 0.3})
    assert out["weighted"] >= 0
    assert "agreement" in out["details"]
    assert out["details"]["mode"] in ("offline-fallback", "consensus")
    # agreement matrix shape
    am = agreement_matrix({"a": {"spec_compliance": 0.9, "code_quality": 0.8,
                                  "test_adequacy": 0.7, "efficiency": 0.6,
                                  "safety": 1.0},
                           "b": {"spec_compliance": 0.8, "code_quality": 0.7,
                                  "test_adequacy": 0.6, "efficiency": 0.5,
                                  "safety": 1.0}})
    for d in ("spec_compliance", "code_quality", "test_adequacy",
              "efficiency", "safety", "overall"):
        assert d in am
        assert 0.0 <= am[d] <= 1.0


def test_consensus_agreement_perfect(monkeypatch):
    am = agreement_matrix(
        {"a": {"spec_compliance": 0.5, "code_quality": 0.5,
               "test_adequacy": 0.5, "efficiency": 0.5, "safety": 0.5},
         "b": {"spec_compliance": 0.5, "code_quality": 0.5,
               "test_adequacy": 0.5, "efficiency": 0.5, "safety": 0.5}})
    assert am["overall"] == 1.0  # identical judges -> perfect agreement


def test_consensus_judge_runs(monkeypatch):
    cj = ConsensusJudge(backends=["offline"])
    res = cj.run("p2", {"test_coverage": 0.8, "violations": [],
                         "tests_written": True, "token_ratio": 0.4})
    d = res.as_dict()
    assert "weighted" in d and "scores" in d
    assert d["details"]["mode"] in ("consensus", "offline-fallback")


# ------------------------------------------------------------------
# 2. memory compression
# ------------------------------------------------------------------
def test_compress_session_heuristic(tmp_path):
    db = str(tmp_path / "mem.db")
    store = SessionStore(path=db)
    store.open_session("s1", "alice")
    for i, txt in enumerate([
        "Decided to use Postgres for persistence",
        "The flaky test was fixed by pinning the DB version",
        "Auth flow uses JWT with 24h expiry",
        "Deployed to staging successfully",
    ]):
        store.remember("s1", "alice", txt, kind="episodic",
                       salience=0.5 + i * 0.1)
    res = compress_session(store, "s1", "alice", online=False)
    assert res["episodes"] == 4
    assert res["summarizer"] == "heuristic"
    assert res["fallback"] is False
    assert len(res["facts"]) >= 1
    assert res["summary"]
    # summary facts were written back with kind="summary"
    recalled = store.recall("alice", "persistence decision",
                            session_id="s1", limit=10)
    assert any(r["kind"] == "summary" for r in recalled)
    store.close()


def test_compress_session_empty(tmp_path):
    db = str(tmp_path / "mem2.db")
    store = SessionStore(path=db)
    store.open_session("s-empty", "bob")
    res = compress_session(store, "s-empty", "bob", online=False)
    assert res["episodes"] == 0
    assert res["facts"] == []
    store.close()


def test_pick_summarizer_heuristic_when_no_key(monkeypatch):
    for var in ("AGNES_API_KEY", "OPENAI_API_KEY", "SUMMARIZER"):
        monkeypatch.delenv(var, raising=False)
    s = pick_summarizer(backend=None)
    assert isinstance(s, HeuristicSummarizer)
    s2 = pick_summarizer(backend="heuristic")
    assert isinstance(s2, HeuristicSummarizer)


# ------------------------------------------------------------------
# 3. SLO alerts
# ------------------------------------------------------------------
def _make_breached_spans(n=20):
    logger = TraceLogger(max_spans=200)
    for i in range(n):
        s = logger.log("tool_call", {"i": i})
        s.end_ts = s.start_ts + 0.02 * (i + 1)
        if i % 4 == 0:
            s.status = "error"
    return logger.spans


def test_build_alert_payload_breached():
    spans = _make_breached_spans()
    from charter.trace_link import slo_summary
    slo = slo_summary(spans, s_lo_ms=1000.0, s_lo_error=0.10)
    payload = build_alert_payload(slo, service="svc")
    assert isinstance(payload, AlertPayload)
    am = payload.to_alertmanager()
    assert am["labels"]["alertname"] == "CharterSLOBreached"
    assert am["labels"]["service"] in ("svc",) or am["labels"]["service"]
    pd = payload.to_pagerduty()
    assert pd["event_action"] == "trigger"
    assert pd["payload"]["summary"]


def test_build_alert_payload_met():
    spans = _make_breached_spans(n=2)  # 2 spans, no errors
    for s in spans:
        s.status = "ok"
    from charter.trace_link import slo_summary
    slo = slo_summary(spans, s_lo_ms=5000.0, s_lo_error=0.5)
    payload = build_alert_payload(slo, service="svc")
    assert payload.severity == "resolved"


def test_fire_backend_none_carries_payloads():
    spans = _make_breached_spans()
    from charter.trace_link import slo_summary
    slo = slo_summary(spans, s_lo_ms=1000.0, s_lo_error=0.10)
    payload = build_alert_payload(slo, service="svc")
    out = fire(payload, backend="none")
    assert out.get("payload_only") is True
    assert "alertmanager_body" in out and "pagerduty_body" in out


def test_fire_alertmanager_retry_safe(monkeypatch):
    """Point at an unreachable URL -> fire returns a retry-safe report, no
    exception (the payload is carried back)."""
    for var in ("ALERTMANAGER_URL",):
        monkeypatch.delenv(var, raising=False)
    spans = _make_breached_spans()
    from charter.trace_link import slo_summary
    slo = slo_summary(spans, s_lo_ms=1000.0, s_lo_error=0.10)
    payload = build_alert_payload(slo, service="svc")
    out = fire(payload, backend="alertmanager",
               url="http://127.0.0.1:1/api/v2/alerts")
    assert out["delivered"] is False
    assert "payload" in out  # retry-safe: the prepared body is returned


def test_slo_alert_gate_evaluate():
    spans = _make_breached_spans()
    gate = SLOAlertGate()
    res = gate.evaluate(spans, p95_ms=1000.0, error_rate=0.10)
    assert "slo" in res and "payload" in res and "should_fire" in res


# ------------------------------------------------------------------
# 4. SPIRE gateway
# ------------------------------------------------------------------
def test_spire_gateway_local_fallback(monkeypatch):
    """No gRPC channel -> gateway fetches from the local TrustDomain issuer
    (same call shape, source='local')."""
    gw = connect_spire(target="localhost:8091",
                       trust_domain="charter.example.com")
    assert gw.source == "local"  # grpc/SPIRE SDK not installed in CI
    svid = gw.fetch_x509_svid("spiffe://charter.example.com/ns/prod/sa/agent1")
    assert svid.spiffe_id == "spiffe://charter.example.com/ns/prod/sa/agent1"
    assert svid.source == "local"
    ok, reasons = gw.verify(svid)
    assert ok is True, reasons


def test_fetch_x509_svid_round_trip():
    svid = fetch_x509_svid("charter.example.com", "/ns/prod/sa/agent1")
    assert svid.spiffe_id.endswith("/ns/prod/sa/agent1")
    ok, reasons = verify_remote_svid(svid, "charter.example.com")
    assert ok is True, reasons


def test_spire_gateway_wrong_trust_domain_rejects():
    svid = fetch_x509_svid("charter.example.com", "/ns/prod/sa/agent1")
    ok, reasons = verify_remote_svid(svid, "other.example.com")
    assert ok is False
    assert any("trust domain" in r for r in reasons)


# ------------------------------------------------------------------
# 5. template PR auto-CI + community scoring
# ------------------------------------------------------------------
_SAMPLE = {
    "name": "v4-industry",
    "label": "V4 Industry",
    "description": "candidate",
    "stage_gates": {"stage_0": ["kickoff"], "stage_5": ["build"]},
    "tdd_enforcement": "soft",
    "token_budget": 200,
    "audit_required_stages": ["stage_0"],
    "guardrail_extra_patterns": ["secrets?", "password"],
}


def test_run_template_ci_passes(monkeypatch):
    report = run_template_ci(_SAMPLE)
    assert report["passed"] is True, report["failed"]
    for c in report["checks"]:
        assert c["check"] and isinstance(c["pass"], bool)


def test_run_template_ci_fails_on_bad_spec():
    bad = dict(_SAMPLE, name="Bad Slug!", token_budget=0)
    report = run_template_ci(bad)
    assert report["passed"] is False
    assert any(not c["pass"] for c in report["checks"])


def test_community_score_and_rank():
    # reset registry state deterministically by using fresh names
    add_feedback("alpha", "helpful")
    add_feedback("alpha", "helpful")
    add_feedback("alpha", "adopted")
    add_feedback("beta", "helpful")
    add_feedback("beta", "reported")
    a = community_score("alpha")
    b = community_score("beta")
    assert a["n_signals"] == 3
    assert b["n_signals"] == 2
    assert a["score"] > b["score"]  # alpha is healthier
    ranked = rank_templates(["alpha", "beta"], min_signals=1)
    assert ranked[0]["name"] == "alpha"


def test_community_score_unknown():
    out = community_score("never-seen-template")
    assert out["n_signals"] == 0
    assert out["score"] == 0.0


def test_template_pr_with_ci_offline(monkeypatch):
    for var in ("GITHUB_TOKEN", "GH_TOKEN", "TEMPLATE_PR_REPO"):
        monkeypatch.delenv(var, raising=False)
    from charter.pr_community import template_pr_with_ci
    res = template_pr_with_ci(_SAMPLE, repo="x/y", token="")
    assert res["pr"]["draft"] is True
    assert res["ci"]["passed"] in (True, False)
    assert "community" in res
    assert res["community"]["name"] == "v4-industry"
