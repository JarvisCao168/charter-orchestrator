"""v3.14: plan_pipeline tool + repair_and_rerun mcp executor + L3 consistency."""
from __future__ import annotations

import json
import http.server
import threading
import urllib.parse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from charter.mcp_server import list_mcp_tools, run_tool
from charter import CriticPlan, CriticStep, repair_and_rerun, mcp_step_executor


# ---------------------------------------------------------------- plan_pipeline

def test_plan_pipeline_tool_present():
    names = {t["name"] for t in list_mcp_tools()}
    assert "plan_pipeline" in names


def test_plan_pipeline_routes_every_step():
    r = run_tool("plan_pipeline", {"plan": {"plan_id": "pp", "goal": "g",
        "steps": [{"id": "fetch"}, {"id": "analyze", "depends_on": ["fetch"]},
                  {"id": "write", "depends_on": ["analyze"]}]}})
    assert r["ok"], r
    res = r["result"]
    assert set(res["routing"].keys()) == {"fetch", "analyze", "write"}
    assert res["critic"]["sound"] is True
    assert res["final_plan"]["plan_id"] == "pp"


def test_plan_pipeline_closed_loop_repairs_before_routing():
    # cycle a<->b: the critic breaks it, then routing runs on the repaired plan
    r = run_tool("plan_pipeline", {"plan": {"plan_id": "pp2", "goal": "g",
        "steps": [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]},
        "closed_loop": True, "max_rounds": 3})
    assert r["ok"], r
    res = r["result"]
    assert res["critic"]["converged"] is True
    # routing decisions exist for every surviving step
    final_ids = [s["id"] for s in res["final_plan"]["steps"]]
    assert set(res["routing"].keys()) == set(final_ids)


def test_plan_pipeline_depth_scales_tier():
    deep = run_tool("plan_pipeline", {"plan": {"plan_id": "pp3", "goal": "g",
        "steps": [{"id": "s1"}, {"id": "s2", "depends_on": ["s1"]},
                  {"id": "s3", "depends_on": ["s2"]}, {"id": "s4", "depends_on": ["s3"]}]},
        "depth_scale": 5, "default_risk": 0.9, "default_tokens": 4000, "closed_loop": False})
    assert deep["ok"]
    leaf = deep["result"]["routing"]["s4"]
    root = deep["result"]["routing"]["s1"]
    assert leaf["cost"] >= root["cost"], (leaf, root)


# ------------------------------------------------- repair_and_rerun mcp executor

def test_mcp_step_executor_is_exported():
    ex = mcp_step_executor()
    assert callable(ex)
    step = CriticStep(id="s", name="route_task", inputs={"depth": 1, "tokens": 100})
    out = ex(step)
    assert "tier" in out, out


def test_repair_and_rerun_mcp_executor_self_heals_cycle():
    plan = CriticPlan(plan_id="heal", goal="g", steps=[
        CriticStep(id="a", name="route_task", inputs={"depth": 1, "tokens": 100}, depends_on=["b"]),
        CriticStep(id="b", name="route_task", inputs={"depth": 1, "tokens": 100}, depends_on=["a"]),
    ])
    report = repair_and_rerun(plan, executor="mcp", max_rounds=3)
    assert report.converged is True
    assert report.rounds >= 1
    h = report.history[0]
    assert h["rerun_steps"] == 2


# ------------------------------------------------------------ L3 consistency

def _kv_server():
    class H(http.server.BaseHTTPRequestHandler):
        store = {}
        def log_message(self, *a):
            pass
        def do_GET(self):
            k = urllib.parse.unquote(self.path.split("/kv/")[-1])
            if k in H.store:
                b = json.dumps(H.store[k]).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            else:
                self.send_response(404)
                self.end_headers()
        def do_POST(self):
            k = urllib.parse.unquote(self.path.split("/kv/")[-1])
            n = int(self.headers.get("Content-Length", 0))
            H.store[k] = json.loads(self.rfile.read(n).decode())
            self.send_response(200)
            self.end_headers()
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_l3_version_stamp_increments():
    from charter import SemanticCache, make_remote_backend
    srv, url = _kv_server()
    try:
        b = make_remote_backend("http", url)
        c = SemanticCache(max_entries=4, remote=b)
        c.put("k", "v1")
        assert c.get_version("k") == 1
        c.put("k", "v2")
        assert c.get_version("k") == 2
        assert c.get("k") == "v2"
        c.close()
    finally:
        srv.shutdown()


def test_l3_cross_instance_version_visible():
    from charter import SemanticCache, make_remote_backend
    srv, url = _kv_server()
    try:
        b1 = make_remote_backend("http", url)
        b2 = make_remote_backend("http", url)
        c1 = SemanticCache(max_entries=4, remote=b1)
        c1.put("k", 42)
        c1.close()
        c2 = SemanticCache(max_entries=4, remote=b2)
        assert c2.get("k") == 42, "L3 miss across instances"
        assert c2.get_version("k") == 1, "version not visible across instances"
        c2.close()
    finally:
        srv.shutdown()


def test_l3_ttl_expiry_is_a_miss():
    from charter import SemanticCache, make_remote_backend
    srv, url = _kv_server()
    try:
        b = make_remote_backend("http", url)
        c1 = SemanticCache(max_entries=4, remote=b)
        c1.put("k", 1)
        c1.close()
        # ttl already elapsed by the time we read (write ts is "now", ttl tiny)
        c2 = SemanticCache(max_entries=4, remote=b, ttl_s=0.0001)
        assert c2.get("k") is None, "expired entry should be a miss"
        c2.close()
    finally:
        srv.shutdown()


def test_get_version_none_for_unknown_key():
    from charter import SemanticCache, make_remote_backend
    srv, url = _kv_server()
    try:
        b = make_remote_backend("http", url)
        c = SemanticCache(max_entries=4, remote=b)
        assert c.get_version("never-written") is None
        c.close()
    finally:
        srv.shutdown()
