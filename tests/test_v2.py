"""v2.0 layer tests: OTel, identity, vector memory, templates."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from charter import (
    to_otlp_json, prometheus_text, GrafanaDashboard,
    IdentityRegistry, issue_agent, sign_tool_call, verify_tool_call,
    VectorMemory, vector_recall, hash_embed,
    list_templates, load_template, apply_template,
)
from charter.observability import TraceLogger, Span


def test_otel_export_shape():
    tl = TraceLogger()
    tl.log("init_project", {"x": 1})
    tl.log("advance_stage", {"y": 2}, parent_id="p1")
    out = to_otlp_json(tl.spans)
    assert "resourceSpans" in out
    rs = out["resourceSpans"][0]
    assert rs["resource"]["attributes"][0]["value"]["stringValue"] == "charter-orchestrator"
    assert len(rs["scopeSpans"][0]["spans"]) == 2
    # OTel-semantic: spans have traceId/spanId
    assert "traceId" in rs["scopeSpans"][0]["spans"][0]


def test_prometheus_metrics():
    tl = TraceLogger()
    for _ in range(3):
        tl.log("init_project")
    tl.log("confirm_gate")
    text = prometheus_text(tl.spans, "proj1")
    assert 'charter_spans_total' in text
    assert 'project_id="proj1"' in text
    assert "charter_tool_calls_total" in text


def test_grafana_dashboard():
    dash = GrafanaDashboard()
    assert dash["title"] == "Charter Orchestrator"
    assert len(dash["panels"]) >= 3


def test_identity_sign_and_verify():
    reg = IdentityRegistry(root_key="test-root")
    issue_agent("alice", ["init_project", "execute_in_sandbox"], registry=reg)
    call = sign_tool_call("alice", "execute_in_sandbox", {"cmd": "ls"}, registry=reg)
    ok = verify_tool_call(call, {"cmd": "ls"}, registry=reg)
    assert ok["ok"], ok
    # tampered payload fails
    bad = verify_tool_call(call, {"cmd": "rm -rf /"}, registry=reg)
    assert not bad["ok"] and any("digest" in p for p in bad["problems"])


def test_identity_replay_blocked():
    reg = IdentityRegistry(root_key="r")
    issue_agent("bob", ["run"], registry=reg)
    call = sign_tool_call("bob", "run", {"a": 1}, registry=reg)
    r1 = verify_tool_call(call, {"a": 1}, registry=reg)
    r2 = verify_tool_call(call, {"a": 1}, registry=reg)  # same nonce
    assert r1["ok"]
    assert not r2["ok"] and "replayed nonce" in r2["problems"]


def test_identity_capability_enforced():
    reg = IdentityRegistry(root_key="r")
    issue_agent("carol", ["read_only"], registry=reg)
    try:
        sign_tool_call("carol", "delete_db", {}, registry=reg)
        assert False, "should raise"
    except PermissionError:
        pass


def test_identity_expired():
    reg = IdentityRegistry(root_key="r")
    issue_agent("dave", ["x"], ttl_s=-1, registry=reg)  # already expired
    call = sign_tool_call("dave", "x", {}, registry=reg)
    r = verify_tool_call(call, {}, registry=reg)
    assert not r["ok"] and "identity expired" in r["problems"]


def test_hash_embed_deterministic_and_dim():
    a = hash_embed("use sqlite for cache", 64)
    b = hash_embed("use sqlite for cache", 64)
    assert a == b
    assert len(a) == 64
    import math
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6  # L2 normalized


def test_vector_memory_semantic_ranking():
    store = VectorMemory(path=":memory:", dim=128)
    store.remember("ag", "we chose SQLite as the cache layer")
    store.remember("ag", "the login flow uses OAuth2")
    store.remember("ag", "deployed the service to kubernetes")
    hits = store.recall("ag", "cache storage decision", limit=3)
    assert hits
    top = hits[0]["content"]
    assert "SQLite" in top, f"expected sqlite top, got {top}"
    # cross-agent isolation
    assert store.recall("other", "cache", limit=3) == []


def test_vector_recall_scores_present():
    store = VectorMemory(path=":memory:")
    store.remember("ag", "use redis for sessions")
    res = store.recall("ag", "session store", limit=1)
    assert "score" in res[0] and "cosine" in res[0]


def test_templates_listed_and_applied():
    names = [t["name"] for t in list_templates()]
    for expected in ["finance", "healthcare", "e-commerce", "research"]:
        assert expected in names, names
    cfg = apply_template({}, "healthcare")
    assert cfg["tdd_enforcement"] == "strict"
    assert cfg["token_budget"] == 50_000
    assert any("phi" in p.lower() for p in cfg["guardrail_extra_patterns"])


def test_template_unknown_raises():
    try:
        load_template("does-not-exist")
        assert False
    except KeyError:
        pass
