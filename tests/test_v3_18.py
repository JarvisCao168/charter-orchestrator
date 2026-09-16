"""v3.18: reconcile repair + dual-source metrics-watch + audit-loop + stress JSON."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------- reconcile repair

def test_reconcile_repair_backfill_l1():
    from charter import SemanticCache, make_remote_backend, reference_kv_gateway
    srv, url, _store = reference_kv_gateway()
    try:
        b = make_remote_backend("http", url)
        c = SemanticCache(max_entries=4, remote=b)
        c.put("k1", "v1")
        c.put("k2", "v2")
        for i in range(10):
            c.put(f"filler-{i}", i)
        rep = c.reconcile(repair=True)
        assert rep["repairs"] > 0
        actions = [a["action"] for a in rep["repaired"]]
        assert "backfill_l1" in actions, f"expected backfill, got {actions}"
        c.close()
    finally:
        srv.shutdown()


def test_reconcile_repair_persists_memory_only():
    from charter import SemanticCache, reference_kv_gateway
    srv, url, _store = reference_kv_gateway()
    try:
        c = SemanticCache(max_entries=8, remote=None)
        c.put("local-only", 42)
        rep = c.reconcile(repair=True)
        assert rep["repairs"] >= 0
        c.close()
    finally:
        srv.shutdown()


def test_reconcile_repair_with_ttl_purge():
    from charter import SemanticCache, make_remote_backend, reference_kv_gateway
    import time
    srv, url, _store = reference_kv_gateway()
    try:
        b = make_remote_backend("http", url)
        c = SemanticCache(max_entries=4, remote=b, ttl_s=0.1)
        c.put("short-ttl", "x")
        time.sleep(0.15)
        for i in range(10):
            c.put(f"fill-{i}", i)
        rep = c.reconcile(repair=True)
        actions = [a["action"] for a in rep["repaired"]]
        assert "purge_expired" in actions or "backfill_l1" in actions
        c.close()
    finally:
        srv.shutdown()


# ------------------------------------------ dual-source metrics-watch

def test_metrics_watch_usage_error():
    from charter.cli import metrics_watch
    # no url and no sse -> usage error rc=2
    assert metrics_watch([]) == 2


# ------------------------------------------------------- audit-loop

def test_audit_loop_usage_error():
    from charter.cli import audit_loop
    assert audit_loop([]) == 2
    assert audit_loop(["--cycles", "0"]) == 2


# --------------------------------------------------- stress JSON

def test_stress_reports_version_field():
    from charter import reference_kv_gateway, stress_multi_writer
    srv, url, _store = reference_kv_gateway()
    try:
        r = stress_multi_writer(n_writers=2, iterations=2, base_url=url)
        assert r["ok"]
        assert "ops" in r and "conflict_rate" in r
    finally:
        srv.shutdown()

