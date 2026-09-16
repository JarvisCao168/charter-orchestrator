"""v3.20: start_sweeper + audit-loop webhook + validate-stress-report --ci + tool+tier labels."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------- start_sweeper

def test_start_sweeper_starts_and_stops():
    from charter import SemanticCache
    c = SemanticCache(max_entries=8, remote=None, ttl_s=0.1)
    c.put("k", 1)
    h = c.start_sweeper(interval_s=0.05)
    assert h.running
    time.sleep(0.15)
    h.stop()
    assert not h.running
    assert h.last_sweep is not None
    assert "swept" in h.last_sweep
    c.close()


def test_start_sweeper_with_reconcile():
    from charter import SemanticCache
    c = SemanticCache(max_entries=8, remote=None, ttl_s=0.1)
    c.put("k", 1)
    h = c.start_sweeper(interval_s=0.05, reconcile=True)
    time.sleep(0.15)
    h.stop()
    assert h.last_reconcile is not None
    assert "consistent" in h.last_reconcile
    c.close()


def test_sweeper_no_ttl_noop():
    from charter import SemanticCache
    c = SemanticCache(max_entries=8, remote=None)
    h = c.start_sweeper(interval_s=0.05)
    time.sleep(0.1)
    h.stop()
    assert h.last_sweep["swept"] == 0
    c.close()


# --------------------------------------- audit-loop webhook

def test_audit_loop_webhook_flags():
    from charter.cli import audit_loop
    # no --pr -> usage error even with webhook flags
    assert audit_loop(["--webhook-url", "http://x/hook"]) == 2
    assert audit_loop(["--webhook-url", "http://x/hook", "--webhook-template", "{}"]) == 2


def test_webhook_post_invalid_url():
    from charter.cli import _webhook_post
    ok, msg = _webhook_post({"text": "hi"}, "http://127.0.0.1:1/never", timeout_s=2)
    assert ok is False


# ------------------------------------ validate-stress-report --ci

def test_validate_stress_report_ci_mode_valid():
    from charter.cli import validate_stress_report
    doc = {"final": 10, "expected": 10, "ok": True, "conflicts": 0,
           "ops": 40, "conflict_rate": 0.0, "wall_s": 0.5,
           "n_writers": 4, "iterations": 10}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(doc, f)
        path = f.name
    rc = validate_stress_report([path, "--ci"])
    assert rc == 0
    os.unlink(path)


def test_validate_stress_report_ci_mode_invalid():
    from charter.cli import validate_stress_report
    doc = {"final": 10}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(doc, f)
        path = f.name
    rc = validate_stress_report([path, "--ci"])
    assert rc == 1
    os.unlink(path)


def test_validate_stress_report_ci_usage_error():
    from charter.cli import validate_stress_report
    assert validate_stress_report(["--ci"]) == 2


# --------------------------------------- tool+tier labels

def test_metrics_payload_tool_tier_labels():
    from charter.mcp_server import HTTPMCPServer, attach_full_governance
    srv = HTTPMCPServer(host="127.0.0.1", port=0)
    attach_full_governance(srv._server)
    with srv._gov_lock:
        srv._gov_gate_pass += 1
        srv._gov_gate_pass_by_tool["route_task"] = 1
        srv._gov_gate_pass_by_tool_tier[("route_task", "high")] = 1
        srv._gov_tracer_spans += 1
        srv._gov_tracer_spans_by_tool_tier[("route_task", "high")] = 1
    text = srv._metrics_payload()["text"]
    assert 'charter_mcp_gate_pass_total{tool="route_task"} 1' in text
    assert 'charter_mcp_gate_pass_total{tool="route_task",tier="high"} 1' in text
    assert 'charter_mcp_tracer_spans_total{tool="route_task",tier="high"} 1' in text


def test_parse_metrics_dual_label():
    from charter.cli import _parse_metrics
    text = 'charter_mcp_gate_fail_total{tool="plan_pipeline",tier="high"} 3\n'
    d = _parse_metrics(text)
    key = 'charter_mcp_gate_fail_total{tool="plan_pipeline",tier="high"}'
    assert d.get(key) == 3.0

