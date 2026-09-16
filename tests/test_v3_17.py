"""v3.17: metrics-watch dashboard + PR audit attach + parameterized CAS + reconcile."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --------------------------------------------------------- metrics-watch

def test_parse_metrics_prometheus_text():
    from charter.cli import _parse_metrics
    sample = ("charter_mcp_gate_pass_total 3\n"
              "charter_mcp_gate_fail_total 1\n"
              "charter_mcp_tracer_spans_total 4\n"
              "charter_mcp_tracer_hallucinations_total 1\n"
              "charter_mcp_tracer_drift_sum 0.25\n")
    d = _parse_metrics(sample)
    assert d["charter_mcp_gate_pass_total"] == 3.0
    assert d["charter_mcp_tracer_drift_sum"] == 0.25


def test_metrics_watch_requires_url():
    from charter.cli import metrics_watch
    assert metrics_watch([]) == 2


def test_attach_audit_to_pr_usage_error():
    from charter.cli import attach_audit_to_pr
    assert attach_audit_to_pr([]) == 2


# ------------------------------------------------------ CAS param stats

def test_stress_reports_conflict_rate_and_ops():
    from charter import reference_kv_gateway, stress_multi_writer
    srv, url, _store = reference_kv_gateway()
    try:
        r = stress_multi_writer(n_writers=4, iterations=10, base_url=url, max_cas_retries=30)
        assert r["ok"]
        assert r["ops"] == 40
        assert r["conflict_rate"] >= 0.0
        assert "wall_s" in r and r["n_writers"] == 4
    finally:
        srv.shutdown()


# ----------------------------------------------------------- reconcile

def test_reconcile_detects_drift():
    from charter import SemanticCache, reference_kv_gateway, make_remote_backend
    srv, url, store = reference_kv_gateway()
    try:
        b = make_remote_backend("http", url)
        c = SemanticCache(max_entries=8, remote=b)
        c.put("a", 1)
        c.put("b", 2)
        rep = c.reconcile()
        assert rep["consistent"] is True
        # force drift: evict one L1 key by exceeding max_entries
        for i in range(20):
            c.put(f"filler-{i}", i)
        rep2 = c.reconcile()
        assert rep2["in_storage_only"], "evicted keys should be flagged storage-only"
        c.close()
    finally:
        srv.shutdown()


def test_http_backend_list_keys():
    from charter import reference_kv_gateway, make_remote_backend
    srv, url, store = reference_kv_gateway()
    try:
        b = make_remote_backend("http", url)
        assert b.list_keys() == []
        c = SemanticCache = None  # noqa
        from charter import SemanticCache
        cc = SemanticCache(max_entries=4, remote=b)
        cc.put("x", 1)
        assert len(b.list_keys()) == 1
        b.close()
        cc.close()
    finally:
        srv.shutdown()
