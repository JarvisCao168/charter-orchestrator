"""v3.15: ETag CAS + plan_pipeline cache + full-tool governance + live subprocess."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------------------------- ETag CAS

def test_cas_no_lost_updates_multi_writer():
    from charter import reference_kv_gateway, stress_multi_writer
    srv, url, store = reference_kv_gateway()
    try:
        res = stress_multi_writer(n_writers=4, iterations=25, base_url=url,
                                  max_cas_retries=30)
        assert res["ok"], res
        assert res["final"] == res["expected"] == 100
    finally:
        srv.shutdown()


def test_put_if_version_412_semantics():
    from charter import reference_kv_gateway, make_remote_backend
    srv, url, store = reference_kv_gateway()
    try:
        b = make_remote_backend("http", url)
        assert b.put_if_version("k", 1, if_version=None) is True   # new write
        assert b.get_version("k") == 1
        assert b.put_if_version("k", 2, if_version=1) is True      # correct ETag
        assert b.get_version("k") == 2
        assert b.put_if_version("k", 3, if_version=1) is False     # stale ETag -> 412
        b.close()
    finally:
        srv.shutdown()


def test_cas_first_write_uses_x_if_new():
    from charter import reference_kv_gateway, make_remote_backend
    srv, url, store = reference_kv_gateway()
    try:
        b = make_remote_backend("http", url)
        ok = b.cas("fresh", read=lambda: b.get("fresh"),
                   write_fn=lambda o, v: 99 if o is None else o + 1, max_retries=5)
        assert ok is True
        raw = b.get("fresh")
        assert raw == 99 or (isinstance(raw, dict) and raw.get("value") == 99)
        b.close()
    finally:
        srv.shutdown()


# ----------------------------------------------------- plan_pipeline cache

def test_plan_pipeline_caches_by_plan_hash():
    from charter.mcp_server import run_tool, _module_pipeline_cache
    _module_pipeline_cache()  # reset lazily per test session
    plan = {"plan_id": "cache-t", "goal": "g",
           "steps": [{"id": "a"}, {"id": "b", "depends_on": ["a"]}],
           "closed_loop": False}
    r1 = run_tool("plan_pipeline", plan)
    assert r1["ok"] and r1["result"].get("cached") is None
    r2 = run_tool("plan_pipeline", plan)
    assert r2["ok"] and r2["result"]["cached"] is True
    # identical decisions on the cached path
    assert r2["result"]["routing"] == r1["result"]["routing"]


def test_configure_pipeline_cache_resets():
    from charter import configure_pipeline_cache
    c = configure_pipeline_cache(max_entries=4, ttl_s=120.0)
    assert c.stats()["ttl_s"] == 120.0


# ------------------------------------------------------- full governance

def test_attach_full_governance_instruments_all_tools():
    from charter.mcp_server import CharterMCPServer, attach_full_governance, list_mcp_tools
    s = CharterMCPServer()
    attach_full_governance(s)
    assert s.gateway is not None
    assert s.semantic_tracer is not None
    assert len(s._tool_contracts) == len(list_mcp_tools())
    # a governed tools/call runs clean (no NameError, trace recorded)
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "query_rule", "arguments": {"rule": "tdd"}}})
    assert "result" in r, r


# ------------------------------------------------------ live subprocess

def test_demo_gov_live_real_cross_process():
    from charter.cli import _demo_governance_live
    rep = _demo_governance_live()
    assert rep["writer_exit"] == 0 and rep["reader_exit"] == 0, rep
    assert rep["cross_process_l3_hit"] is True, rep
    assert "hits: 1" in rep["reader_out"]
