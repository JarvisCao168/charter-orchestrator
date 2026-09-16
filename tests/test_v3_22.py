"""v3.22: start_sweeper auto-register + webhook SQLite persistence + stress TIER=custom + dashboard tier table."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------- auto-register

def test_start_sweeper_auto_registers():
    """v3.22: start_sweeper(http_server=...) calls register_sweeper automatically."""
    from charter import SemanticCache
    from charter.mcp_server import HTTPMCPServer, attach_full_governance
    srv = HTTPMCPServer(host="127.0.0.1", port=0)
    attach_full_governance(srv._server)
    assert srv._sweeper_handle is None
    c = SemanticCache(max_entries=8, remote=None, ttl_s=0.1)
    h = c.start_sweeper(interval_s=0.05, http_server=srv)
    assert srv._sweeper_handle is not None
    assert srv._sweeper_handle is h
    time.sleep(0.1)
    h.stop()
    # /metrics should now include charter_sweeper_* lines
    text = srv._metrics_payload()["text"]
    assert "charter_sweeper_sweeps_total" in text
    c.close()


# --------------------------------------- webhook SQLite

def test_webhook_persistence_roundtrip():
    """v3.22: enqueue -> persist to SQLite -> restore from SQLite (simulated crash)."""
    import charter.cli as _cli
    import sqlite3
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "webhook.db")
        _cli._webhook_set_db_path(db_path)
        try:
            _cli._WEBHOOK_RETRY_QUEUE.clear()
            # Enqueue a retry
            _cli._webhook_enqueue_retry({"text": "test"}, "http://x/hook", 1, 0.0)
            assert len(_cli._WEBHOOK_RETRY_QUEUE) == 1
            # Simulate crash: clear in-memory queue
            _cli._WEBHOOK_RETRY_QUEUE.clear()
            # Restore from DB
            n = _cli._webhook_restore_from_db()
            assert n == 1, f"expected 1 restored, got {n}"
            assert _cli._WEBHOOK_RETRY_QUEUE[0][1] == "http://x/hook"
        finally:
            _cli._webhook_set_db_path("")
            _cli._WEBHOOK_RETRY_QUEUE.clear()


def test_webhook_persistence_no_db():
    """v3.22: without a DB path, restore returns 0 and persist is a no-op."""
    import charter.cli as _cli
    _cli._webhook_set_db_path("")
    n = _cli._webhook_restore_from_db()
    assert n == 0


# ------------------------------------ stress TIER=custom

def test_stress_returns_n_and_i_fields():
    """v3.22: stress_multi_writer output includes n_writers and iterations for TIER=custom."""
    from charter import reference_kv_gateway, stress_multi_writer
    srv, url, _store = reference_kv_gateway()
    try:
        r = stress_multi_writer(n_writers=8, iterations=50, base_url=url, max_cas_retries=30)
        assert r["n_writers"] == 8
        assert r["iterations"] == 50
        assert r["ok"]
    finally:
        srv.shutdown()


# --------------------------------------- tier table render

def test_metrics_watch_tier_breakdown_parse():
    """v3.22: _parse_metrics handles dual-label lines; tier_breakdown JSON parse works."""
    from charter.cli import _parse_metrics
    text = (
        'charter_mcp_gate_pass_total{tool="route_task",tier="high"} 3\n'
        'charter_mcp_gate_fail_total{tool="plan_pipeline",tier="low"} 1\n'
        'charter_mcp_gate_pass_total 5\n'
    ).replace("\\n", "\n")
    d = _parse_metrics(text)
    assert d.get('charter_mcp_gate_pass_total{tool="route_task",tier="high"}') == 3.0
    assert d.get('charter_mcp_gate_fail_total{tool="plan_pipeline",tier="low"}') == 1.0
    assert d.get("charter_mcp_gate_pass_total") == 5.0


def test_tier_breakdown_json_roundtrip():
    """v3.22: tier_breakdown dict can be JSON-serialised and re-parsed (SSE data line)."""
    tb = {"high": {"gate_pass:route_task": 3, "gate_fail:route_task": 1},
            "low": {"gate_pass:plan_pipeline": 5}}
    s = json.dumps(tb, ensure_ascii=False)
    tb2 = json.loads(s)
    assert tb2 == tb

