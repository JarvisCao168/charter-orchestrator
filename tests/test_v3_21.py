"""v3.21: sweeper stats + webhook retry queue + stress tier + SSE tier_breakdown."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------- sweeper stats

def test_sweeper_handle_stats():
    from charter import SemanticCache
    c = SemanticCache(max_entries=8, remote=None, ttl_s=0.1)
    c.put("k", 1)
    h = c.start_sweeper(interval_s=0.05, reconcile=True)
    time.sleep(0.15)
    st = h.stats()
    assert st["sweeps_total"] >= 1
    assert "keys_swept_total" in st
    assert st["uptime_s"] >= 0.1
    assert st["running"] is True
    h.stop()
    st2 = h.stats()
    assert st2["running"] is False
    c.close()


def test_sweeper_stats_no_ttl():
    from charter import SemanticCache
    c = SemanticCache(max_entries=8, remote=None)
    h = c.start_sweeper(interval_s=0.05)
    time.sleep(0.1)
    st = h.stats()
    assert st["keys_swept_total"] == 0
    h.stop()
    c.close()


# --------------------------------------- webhook retry

def test_webhook_enqueue_and_process():
    from charter.cli import _webhook_enqueue_retry, _webhook_process_retries
    import charter.cli as _cli
    # Clear the queue first
    _cli._WEBHOOK_RETRY_QUEUE.clear()
    # Enqueue an item with immediate retry (delay=0)
    _webhook_enqueue_retry({"text": "hi"}, "http://127.0.0.1:1/never", 1, 0.0)
    n = _webhook_process_retries()
    # The POST will fail (port 1 is closed) so it gets re-enqueued
    assert n == 0
    _cli._WEBHOOK_RETRY_QUEUE.clear()


def test_webhook_retry_queue_isolated():
    import charter.cli as _cli
    _cli._WEBHOOK_RETRY_QUEUE.clear()
    assert len(_cli._WEBHOOK_RETRY_QUEUE) == 0


# ------------------------------------ stress tier field

def test_stress_multi_writer_returns_n_writers():
    from charter import reference_kv_gateway, stress_multi_writer
    srv, url, _store = reference_kv_gateway()
    try:
        r = stress_multi_writer(n_writers=2, iterations=2, base_url=url, max_cas_retries=30)
        assert r["n_writers"] == 2
        assert r["iterations"] == 2
        assert "ops" in r and "conflict_rate" in r and "wall_s" in r
    finally:
        srv.shutdown()


# --------------------------------------- SSE tier_breakdown

def test_metrics_payload_includes_tier_breakdown_structure():
    """v3.21: after simulated tool+tier counters, _metrics_payload text has
    dual-label lines AND the tier breakdown is accessible via the dict."""
    from charter.mcp_server import HTTPMCPServer, attach_full_governance
    srv = HTTPMCPServer(host="127.0.0.1", port=0)
    attach_full_governance(srv._server)
    with srv._gov_lock:
        srv._gov_gate_pass_by_tool_tier[("route_task", "high")] = 1
        srv._gov_tracer_spans_by_tool_tier[("route_task", "high")] = 1
    text = srv._metrics_payload()["text"]
    assert 'charter_mcp_gate_pass_total{tool="route_task",tier="high"} 1' in text


def test_webhook_post_failure_returns_false():
    from charter.cli import _webhook_post
    ok, msg = _webhook_post({"text": "test"}, "http://127.0.0.1:1/x", timeout_s=2)
    assert ok is False
    assert msg  # some error message

