"""v3.19: sweep_expired + audit-loop health/dry-run + validate-stress-report + tool-label metrics."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------- sweep_expired

def test_sweep_expired_no_ttl():
    from charter import SemanticCache
    c = SemanticCache(max_entries=8, remote=None)
    c.put("k", 1)
    rep = c.sweep_expired()
    assert rep["swept"] == 0
    assert rep["ttl_s"] is None
    c.close()


def test_sweep_expired_purges_l1():
    from charter import SemanticCache
    import time
    c = SemanticCache(max_entries=8, remote=None, ttl_s=0.1)
    c.put("old-key", "x")
    time.sleep(0.15)
    rep = c.sweep_expired()
    assert rep["swept"] >= 1
    # The key is stored under its semantic hash; just check count and cache empty
    assert len(c._peek()) == 0, f"cache not empty after sweep: {c._peek()}"
    c.close()


def test_sweep_expired_purges_l2():
    import tempfile, time
    from charter import SemanticCache
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "cache.db")
        c = SemanticCache(max_entries=8, disk_path=db, ttl_s=0.1)
        c.put("disk-key", 42)
        time.sleep(0.15)
        rep = c.sweep_expired()
        assert rep["swept"] >= 1
        assert len(rep["l2_swept"]) >= 1, f"l2_swept={rep['l2_swept']}"
        c.close()


# --------------------------------------- audit-loop flags

def test_audit_loop_dry_run_flag():
    from charter.cli import audit_loop
    assert audit_loop([]) == 2
    assert audit_loop(["--dry-run"]) == 2


def test_audit_loop_metrics_url_flag():
    from charter.cli import audit_loop
    assert audit_loop(["--metrics-url", "http://x/metrics"]) == 2


# ------------------------------------ validate-stress-report

def test_validate_stress_report_valid():
    import tempfile
    from charter.cli import validate_stress_report
    doc = {"final": 10, "expected": 10, "ok": True, "conflicts": 0,
           "ops": 40, "conflict_rate": 0.0, "wall_s": 0.5,
           "n_writers": 4, "iterations": 10}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(doc, f)
        path = f.name
    assert validate_stress_report([path]) == 0
    os.unlink(path)


def test_validate_stress_report_missing_field():
    import tempfile
    from charter.cli import validate_stress_report
    doc = {"final": 10, "ok": True}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(doc, f)
        path = f.name
    assert validate_stress_report([path]) == 1
    os.unlink(path)


def test_validate_stress_report_usage_error():
    from charter.cli import validate_stress_report
    assert validate_stress_report([]) == 2


# --------------------------------------- per-tool metrics

def test_parse_metrics_labeled_tool_metric():
    from charter.cli import _parse_metrics
    text = 'charter_mcp_gate_fail_total{tool="plan_pipeline"} 2\n'
    d = _parse_metrics(text)
    assert d.get('charter_mcp_gate_fail_total{tool="plan_pipeline"}') == 2.0


def test_http_server_emits_tool_labels():
    """v3.19: _metrics_payload() includes per-tool {tool=...} labeled lines."""
    import json as _j
    from charter.mcp_server import HTTPMCPServer, attach_full_governance

    srv = HTTPMCPServer(host="127.0.0.1", port=0)
    attach_full_governance(srv._server)
    # Simulate a tool call by incrementing the per-tool counters directly
    with srv._gov_lock:
        srv._gov_gate_pass += 1
        srv._gov_gate_pass_by_tool["route_task"] = 1
        srv._gov_tracer_spans += 1
        srv._gov_tracer_spans_by_tool["route_task"] = 1
    text = srv._metrics_payload()["text"]
    assert "charter_mcp_gate_pass_total" in text
    assert 'charter_mcp_gate_pass_total{tool="route_task"} 1' in text, text[:800]
    assert 'charter_mcp_tracer_spans_total{tool="route_task"} 1' in text, text[:800]

