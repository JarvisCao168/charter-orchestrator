"""v3.16: audit replay export + shared pipeline L3 + governance metrics + CAS stress."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------- audit replay

def test_tracer_to_json_roundtrip():
    from charter import SemanticTracer, export_audit_report
    tracer = SemanticTracer(threshold=0.2)
    tracer.record("g", "2024 global market size in dollars", "the 2024 global market size is 500 billion dollars", tool="t")
    tracer.record("b", "2024 global market size in dollars", "unrelated text about cooking pasta", tool="t")
    doc = json.loads(tracer.to_json())
    assert doc["tracer"] == "SemanticTracer"
    assert doc["summary"]["spans"] == 2
    good = next(s for s in doc["spans"] if s["span_id"] == "g")
    bad = next(s for s in doc["spans"] if s["span_id"] == "b")
    assert good["verdict"] == "ok", good
    assert bad["verdict"] == "hallucination", bad


def test_export_audit_report_writes_file():
    from charter import SemanticTracer, export_audit_report
    tracer = SemanticTracer(threshold=0.2)
    tracer.record("s1", "q", "relevant answer")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "audit.json")
        out = export_audit_report(tracer, path)
        assert out == path and os.path.isfile(path)
        doc = json.load(open(path, encoding="utf-8"))
        assert doc["summary"]["spans"] == 1


# ------------------------------------------------- shared pipeline L3

def test_demo_pipeline_l3_live_shared_hit():
    from charter.cli import _demo_pipeline_l3_live
    rep = _demo_pipeline_l3_live()
    assert rep["node_a_exit"] == 0 and rep["node_b_exit"] == 0, rep
    assert rep["shared_l3_hit"] is True, rep
    assert "cached: False" in rep["node_a"] and "cached: True" in rep["node_b"]
    # routing is non-empty on both sides (real decisions, not empty shells)
    assert "routing: 3" in rep["node_a"] and "routing: 3" in rep["node_b"]


# ------------------------------------------------ governance metrics

def test_governance_metrics_in_metrics_payload():
    from charter.mcp_server import HTTPMCPServer, attach_full_governance
    srv = HTTPMCPServer(host="127.0.0.1", port=0)
    attach_full_governance(srv._server)
    # call a tool through the governed inner server
    srv._server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "init_project", "arguments": {"project_id": "m1"}}})
    srv._server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                       "params": {"name": "query_rule", "arguments": {"rule": "tdd"}}})
    payload = srv._metrics_payload()["text"]
    assert "charter_mcp_gate_pass_total" in payload
    assert "charter_mcp_gate_fail_total" in payload
    assert "charter_mcp_tracer_spans_total" in payload
    assert "charter_mcp_tracer_drift_sum" in payload
    # two calls, both gated + traced
    assert "charter_mcp_tracer_spans_total 2" in payload
    assert "charter_mcp_gate_pass_total 2" in payload


# -------------------------------------------------------- CAS stress

def test_cas_stress_no_lost_updates():
    from charter import reference_kv_gateway, stress_multi_writer
    srv, url, store = reference_kv_gateway()
    try:
        res = stress_multi_writer(n_writers=4, iterations=25, base_url=url,
                                  max_cas_retries=30)
        assert res["ok"] and res["final"] == res["expected"] == 100, res
    finally:
        srv.shutdown()
