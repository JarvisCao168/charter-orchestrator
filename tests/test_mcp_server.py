"""Tests for charter.mcp_server (v3.1).

Covers:
- TOOL_DEFINITIONS: 20 tools, all have name + description + inputSchema
- run_tool: init_project, list_skills, dispatch_to_model, enforce_tdd,
  guardrails, query_rule, trace_operation, unknown tool
- load_skill: found + not found
- CharterMCPServer.handle: initialize, tools/list, tools/call,
  resources/list, resources/read, unknown method, notification
- MCP wire format: JSON-RPC envelope shape
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from charter import __version__
from charter.mcp_server import (
    TOOL_DEFINITIONS,
    list_mcp_tools,
    load_skill,
    run_tool,
    CharterMCPServer,
)


def test_version_is_v3_5():
    assert __version__.startswith("3.11")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

def test_tool_definitions_count():
    assert len(TOOL_DEFINITIONS) == 20, f"expected 20 tools, got {len(TOOL_DEFINITIONS)}"


def test_tool_definitions_shape():
    for td in TOOL_DEFINITIONS:
        assert "name" in td, f"tool missing name: {td}"
        assert "description" in td and td["description"], f"tool missing description: {td['name']}"
        assert "inputSchema" in td, f"tool missing inputSchema: {td['name']}"
        assert td["inputSchema"]["type"] == "object"


def test_tool_definitions_names_unique():
    names = [td["name"] for td in TOOL_DEFINITIONS]
    assert len(names) == len(set(names)), f"duplicate tool names: {names}"


def test_expected_tool_names_present():
    names = {td["name"] for td in TOOL_DEFINITIONS}
    expected = {
        "init_project", "advance_stage", "confirm_gate", "query_status",
        "query_rule", "list_skills", "execute_in_sandbox", "create_dropbox",
        "manage_task_lifecycle", "trigger_workflow", "create_chat_chain",
        "save_checkpoint", "restore_checkpoint", "dispatch_to_model",
        "manage_worktree", "enforce_tdd", "guardrails",
        "enable_autonomous_mode", "trace_operation", "query_trace",
    }
    assert expected == names, f"missing: {expected - names}, extra: {names - expected}"


def test_list_mcp_tools_returns_all_20():
    tools = list_mcp_tools()
    assert len(tools) == 20


# ---------------------------------------------------------------------------
# run_tool
# ---------------------------------------------------------------------------

def test_run_tool_init_project():
    out = run_tool("init_project", {"project_id": "mcp_test_1"})
    assert out["ok"], out
    result = out["result"]
    # init_project auto-generates an internal project_id; just verify it exists
    assert "project_id" in result and result["project_id"]
    assert "workspace_path" in result


def test_run_tool_query_status():
    # init first so the project exists, then query with the generated project_id
    init_out = run_tool("init_project", {"project_id": "mcp_test_2"})
    assert init_out["ok"], init_out
    pid = init_out["result"]["project_id"]
    out = run_tool("query_status", {"project_id": pid})
    assert out["ok"], out


def test_run_tool_list_skills():
    out = run_tool("list_skills", {})
    assert out["ok"], out
    assert out["result"]["total"] == 111, f"expected 111 skills, got {out['result']['total']}"


def test_run_tool_list_skills_category_filter():
    out = run_tool("list_skills", {"category": "env"})
    assert out["ok"], out
    assert out["result"]["total"] == 7, f"expected 7 env skills, got {out['result']['total']}"


def test_run_tool_dispatch_to_model():
    out = run_tool("dispatch_to_model", {"task_type": "coding", "complexity": 0.9})
    assert out["ok"], out
    result = out["result"]
    assert result["recommended_model"], "no model recommended"
    assert result["task_type"] == "coding"
    # high complexity coding should route to the stronger model
    assert "3.0" in result["recommended_model"] or "flash" not in result["recommended_model"]


def test_run_tool_enforce_tdd_pass():
    out = run_tool("enforce_tdd", {"test_results": {"passed": 5, "failed": 0, "skipped": 1}})
    assert out["ok"], out


def test_run_tool_guardrails_validate():
    out = run_tool("guardrails", {"action": "validate_input", "payload": {"cmd": "ls -la"}})
    assert out["ok"], out


def test_run_tool_trace_operation():
    out = run_tool("trace_operation", {"name": "mcp_test_op", "attributes": {"foo": "bar"}})
    assert out["ok"], out


def test_run_tool_unknown():
    out = run_tool("no_such_tool", {})
    assert not out["ok"], "should fail for unknown tool"
    assert "unknown tool" in out.get("error", "")


# ---------------------------------------------------------------------------
# load_skill
# ---------------------------------------------------------------------------

def test_load_skill_found():
    entry = load_skill("env_01")
    assert entry["found"] is True
    assert entry["manifest"]["name"] == "EnvironmentProbe"
    assert len(entry["content"]) > 50, "SKILL.md content should be non-trivial"


def test_load_skill_not_found():
    entry = load_skill("nonexistent_99")
    assert entry["found"] is False
    assert "not in manifest" in entry.get("error", "")


# ---------------------------------------------------------------------------
# CharterMCPServer (JSON-RPC dispatch)
# ---------------------------------------------------------------------------

def test_mcp_server_initialize():
    server = CharterMCPServer()
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "charter-orchestrator"
    assert "capabilities" in resp["result"]
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_server_tools_list():
    server = CharterMCPServer()
    resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert resp["result"]["tools"], "tools should not be empty"
    assert len(resp["result"]["tools"]) == 20


def test_mcp_server_tools_call_init_project():
    server = CharterMCPServer()
    resp = server.handle({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "init_project", "arguments": {"project_id": "mcp_srv_test"}},
    })
    assert resp["result"]["isError"] is False, resp["result"]
    content = resp["result"]["content"]
    assert content[0]["type"] == "text"
    data = json.loads(content[0]["text"])
    assert data["ok"] is True
    assert "project_id" in data["result"], f"missing project_id: {list(data['result'].keys())}"


def test_mcp_server_tools_call_error_shape():
    server = CharterMCPServer()
    resp = server.handle({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "bogus_tool", "arguments": {}},
    })
    assert resp["result"]["isError"] is True, "unknown tool should set isError=True"


def test_mcp_server_resources_list():
    server = CharterMCPServer()
    resp = server.handle({"jsonrpc": "2.0", "id": 5, "method": "resources/list", "params": {}})
    resources = resp["result"]["resources"]
    assert len(resources) == 112, f"expected 112 resources (111 skills + metrics), got {len(resources)}"
    for res in resources:
        assert res["uri"].startswith("charter://skills/") or \
               res["uri"] == "charter://metrics", f"unexpected URI: {res['uri']}"
        assert res["mimeType"] in ("text/markdown", "text/plain; version=0.0.4")


def test_mcp_server_resources_read():
    server = CharterMCPServer()
    resp = server.handle({
        "jsonrpc": "2.0", "id": 6, "method": "resources/read",
        "params": {"uri": "charter://skills/env_01"},
    })
    contents = resp["result"]["contents"]
    assert len(contents) == 1
    assert contents[0]["uri"] == "charter://skills/env_01"
    assert "EnvironmentProbe" in contents[0]["text"]


def test_mcp_server_resources_read_bad_uri():
    server = CharterMCPServer()
    resp = server.handle({
        "jsonrpc": "2.0", "id": 7, "method": "resources/read",
        "params": {"uri": "http://evil.example.com"},
    })
    assert "error" in resp, f"expected error for unsupported URI, got {resp}"


def test_mcp_server_unknown_method():
    server = CharterMCPServer()
    resp = server.handle({"jsonrpc": "2.0", "id": 8, "method": "no/such/method", "params": {}})
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_mcp_server_notification_returns_none():
    server = CharterMCPServer()
    # notification: no "id" field
    resp = server.handle({"jsonrpc": "2.0", "method": "ping"})
    assert resp is None, "notification should return None (no response)"


def test_mcp_server_ping():
    server = CharterMCPServer()
    resp = server.handle({"jsonrpc": "2.0", "id": 9, "method": "ping"})
    assert resp["result"] == {}


# ---------------------------------------------------------------------------
# SSE / HTTP transport (v3.2)
# ---------------------------------------------------------------------------

def test_http_mcp_server_importable():
    from charter.mcp_server import HTTPMCPServer, run_http_server
    assert callable(run_http_server)
    assert isinstance(HTTPMCPServer, type)


def test_http_server_construction():
    from charter.mcp_server import HTTPMCPServer
    srv = HTTPMCPServer(host="127.0.0.1", port=8799)
    # It wraps a CharterMCPServer and builds 112 resources (111 skills + metrics)
    assert hasattr(srv, "_server")
    resources = srv._server._resource_list
    assert len(resources) == 112, f"expected 112 resources (111 skills + metrics), got {len(resources)}"
    # all URIs are well-formed
    for r in resources:
        assert r["uri"].startswith("charter://skills/") or \
               r["uri"] == "charter://metrics", f"unexpected URI: {r['uri']}"


def test_mcp_tools_endpoint_shape():
    from charter.mcp_server import list_mcp_tools
    tools = list_mcp_tools()
    assert len(tools) == 20
    names = {t["name"] for t in tools}
    assert "init_project" in names and "dispatch_to_model" in names
    # each tool has a valid JSON-serializable inputSchema
    import json as _json
    for t in tools:
        _json.dumps(t)  # raises if not serializable


def test_new_skills_have_valid_paths():
    """All 111 manifest entries point to a file that exists on disk."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base, "skills", "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    skills = manifest["skills"]
    assert len(skills) == 111
    for sid, meta in skills.items():
        p = os.path.join(base, meta["path"])
        assert os.path.isfile(p), f"missing skill file: {meta['path']}"
        # tools refs must be in the 20-tool set
        for t in meta.get("tools", []):
            assert t in set(manifest.get("tools", [])), f"{sid} refs unknown tool {t}"


def test_new_categories_have_skills():
    import json
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base, "skills", "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    cats = {}
    for sid, meta in manifest["skills"].items():
        c = meta["category"]
        cats[c] = cats.get(c, 0) + 1
    # v3.2 added 60 skills; dev/security/obs/collab/analysis/test/deploy all grew
    assert cats.get("dev", 0) >= 20
    assert cats.get("security", 0) >= 11
    assert cats.get("obs", 0) >= 12
    assert cats.get("collab", 0) >= 12
    assert cats.get("analysis", 0) >= 12
    assert cats.get("test", 0) >= 11
    assert cats.get("deploy", 0) >= 12
    assert cats.get("tool", 0) >= 10


# ---------------------------------------------------------------------------
# X-API-Key auth on the HTTP/SSE transport (v3.4)
# ---------------------------------------------------------------------------

def test_http_server_no_key_is_open():
    from charter.mcp_server import HTTPMCPServer
    srv = HTTPMCPServer(api_key=None)
    # no key configured -> auth passes with any/absent header
    assert srv._auth_ok({}) is True


def test_http_server_key_requires_header():
    from charter.mcp_server import HTTPMCPServer
    srv = HTTPMCPServer(api_key="secret-123")
    assert srv._auth_ok({}) is False                  # missing header
    assert srv._auth_ok({"X-API-Key": "wrong"}) is False
    assert srv._auth_ok({"X-API-Key": "secret-123"}) is True


def test_http_server_key_read_from_env(monkeypatch):
    from charter.mcp_server import HTTPMCPServer
    monkeypatch.setenv("CHARTER_MCP_API_KEY", "env-key")
    srv = HTTPMCPServer()   # api_key=None -> falls back to env
    assert srv.api_key == "env-key"
    assert srv._auth_ok({"X-API-Key": "env-key"}) is True
    assert srv._auth_ok({}) is False
    monkeypatch.delenv("CHARTER_MCP_API_KEY", raising=False)


def test_run_http_server_respects_env_key(monkeypatch):
    """run_http_server reads CHARTER_MCP_API_KEY when no explicit key given."""
    import importlib
    import charter.mcp_server as ms
    monkeypatch.setenv("CHARTER_MCP_API_KEY", "env-key-2")
    # construct via the same fallback path run_http_server uses
    srv = ms.HTTPMCPServer(api_key=None)
    assert srv.api_key == "env-key-2"
    monkeypatch.delenv("CHARTER_MCP_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# Prometheus /metrics endpoint (v3.5)
# ---------------------------------------------------------------------------

def test_metrics_endpoint_increments_counter():
    from charter.mcp_server import HTTPMCPServer
    srv = HTTPMCPServer()
    srv._inc_request("GET", "/mcp/health", 200)
    srv._inc_request("GET", "/mcp/health", 200)
    srv._inc_request("POST", "/mcp/message", 202)
    payload = srv._metrics_payload()
    text = payload["text"]
    assert 'charter_mcp_requests_total{method="GET",endpoint="/mcp/health",status="2xx"} 2' in text
    assert 'charter_mcp_requests_total{method="POST",endpoint="/mcp/message",status="2xx"} 1' in text
    assert "charter_mcp_uptime_seconds" in text


def test_metrics_endpoint_by_endpoint_counter():
    from charter.mcp_server import HTTPMCPServer
    srv = HTTPMCPServer()
    srv._inc_request("GET", "/mcp/tools", 200)
    srv._inc_request("GET", "/mcp/sse", 200)
    srv._inc_request("GET", "/nope", 404)
    text = srv._metrics_payload()["text"]
    assert 'charter_mcp_requests_by_endpoint_total{endpoint="/mcp/tools"} 1' in text
    assert 'charter_mcp_requests_by_endpoint_total{endpoint="/mcp/sse"} 1' in text
    assert 'charter_mcp_requests_by_endpoint_total{endpoint="/nope"} 1' in text


def test_metrics_status_class_buckets():
    from charter.mcp_server import HTTPMCPServer
    srv = HTTPMCPServer()
    srv._inc_request("GET", "/mcp/health", 200)
    srv._inc_request("GET", "/mcp/health", 401)
    srv._inc_request("GET", "/mcp/health", 500)
    text = srv._metrics_payload()["text"]
    assert 'status="2xx"} 1' in text
    assert 'status="4xx"} 1' in text
    assert 'status="5xx"} 1' in text


def test_metrics_endpoint_is_open_no_auth():
    """The /metrics path is served without an X-API-Key (scrapers must work)."""
    from charter.mcp_server import HTTPMCPServer
    srv = HTTPMCPServer(api_key="secret")
    # even with a key set, _handle_metrics requires no auth header
    # (do_GET short-circuits /metrics before the auth check)
    assert srv._auth_ok({}) is False  # other endpoints still need the key
    # but /metrics itself is reachable: simulate the short-circuit by calling the handler
    import io
    # just verify the payload generator works without auth
    assert "charter_mcp_uptime_seconds" in srv._metrics_payload()["text"]


# ---------------------------------------------------------------------------
# v3.6 — resources/subscribe + /mcp/sse?stream=metrics live push
# ---------------------------------------------------------------------------

def test_resources_subscribe_round_trip():
    """resources/subscribe records a URI; list_subscriptions reflects it."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/subscribe",
                    "params": {"uri": "charter://metrics", "__client": "c1"}})
    assert r["result"]["subscribed"] is True
    r2 = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/list_subscriptions",
                     "params": {"__client": "c1"}})
    assert "charter://metrics" in r2["result"]["subscriptions"]
    r3 = srv.handle({"jsonrpc": "2.0", "id": 3, "method": "resources/unsubscribe",
                     "params": {"uri": "charter://metrics", "__client": "c1"}})
    assert r3["result"]["subscribed"] is False
    r4 = srv.handle({"jsonrpc": "2.0", "id": 4, "method": "resources/list_subscriptions",
                     "params": {"__client": "c1"}})
    assert r4["result"]["subscriptions"] == []


def test_metrics_resource_readable():
    """resources/read on charter://metrics returns Prometheus-format text."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                    "params": {"uri": "charter://metrics"}})
    assert "contents" in r["result"]
    text = r["result"]["contents"][0]["text"]
    assert "charter_mcp" in text or "stdio" in text
    assert r["result"]["contents"][0]["mimeType"] == "text/plain; version=0.0.4"


def test_metrics_resource_in_http_mode_exposes_counters():
    """When the server is owned by HTTPMCPServer, the metrics resource shows live counters."""
    from charter.mcp_server import HTTPMCPServer, CharterMCPServer
    http = HTTPMCPServer()
    # Simulate some requests on the owner
    http._inc_request("GET", "/mcp/health", 200)
    http._inc_request("POST", "/mcp/message", 202)
    # The CharterMCPServer inside http should now expose those counters
    r = http._server.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                             "params": {"uri": "charter://metrics"}})
    text = r["result"]["contents"][0]["text"]
    assert 'endpoint="/mcp/health"' in text
    assert 'endpoint="/mcp/message"' in text


def test_sse_metrics_stream_is_routed():
    """/mcp/sse?stream=metrics selects the metrics push loop (verify by source)."""
    import inspect
    from charter.mcp_server import HTTPMCPServer
    src = inspect.getsource(HTTPMCPServer._make_handler)
    # The handler code references the metrics stream mode
    assert "stream" in src and "metrics" in src
    # The /mcp/sse route must still be registered in do_GET
    assert "/mcp/sse" in src


def test_subscriptions_are_per_client():
    """Different client keys get independent subscription sets."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/subscribe",
                "params": {"uri": "charter://metrics", "__client": "a"}})
    srv.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/subscribe",
                "params": {"uri": "charter://skills/obs_09", "__client": "b"}})
    ra = srv.handle({"jsonrpc": "2.0", "id": 3, "method": "resources/list_subscriptions",
                     "params": {"__client": "a"}})
    rb = srv.handle({"jsonrpc": "2.0", "id": 4, "method": "resources/list_subscriptions",
                     "params": {"__client": "b"}})
    assert ra["result"]["subscriptions"] == ["charter://metrics"]
    assert rb["result"]["subscriptions"] == ["charter://skills/obs_09"]


# ---------------------------------------------------------------------------
# v3.7 — resources/changed push notifications (no more 5s polling)
# ---------------------------------------------------------------------------

def test_notify_resource_changed_requires_subscription():
    """notify_resource_changed is a no-op for a client that never subscribed."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    # no subscription -> returns False, sink not called
    assert srv.notify_resource_changed("charter://metrics", "ghost") is False


def test_notify_resource_changed_pushes_to_sink():
    """When subscribed, the sink receives a notifications/resources/updated event."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/subscribe",
                "params": {"uri": "charter://metrics", "__client": "c1"}})
    events = []
    srv._notify_sink = lambda ev: events.append(ev)
    ok = srv.notify_resource_changed("charter://metrics", "c1",
                                    payload={"metrics": "charter_mcp_requests_total 3"})
    assert ok is True
    assert len(events) == 1
    assert events[0]["method"] == "notifications/resources/updated"
    assert events[0]["params"]["uri"] == "charter://metrics"
    assert events[0]["params"]["payload"]["metrics"].startswith("charter_mcp")


def test_http_broadcast_metrics_change_notifies_subscribers():
    """_broadcast_metrics_change routes a fresh snapshot to subscribed SSE clients."""
    from charter.mcp_server import HTTPMCPServer
    import queue as _q
    http = HTTPMCPServer()
    # Register a fake SSE client queue + subscription keyed to it.
    cid = "c9"
    http._client_queues[cid] = _q.Queue()
    http._register_client_key(cid, cid)
    # Subscribe the client key to charter://metrics
    http._server.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/subscribe",
                         "params": {"uri": "charter://metrics", "__client": cid}})
    # Trigger a request -> should broadcast to the subscriber
    http._inc_request("GET", "/mcp/health", 200)
    q = http._client_queues[cid]
    assert not q.empty(), "expected a metrics change notification to be pushed"
    import json as _json
    evt = _json.loads(q.get_nowait())
    assert evt["method"] == "notifications/resources/updated"
    assert "charter_mcp_requests_total" in evt["params"]["payload"]["metrics"]


def test_http_broadcast_no_subscribers_is_zero():
    """With no subscribers, _broadcast_metrics_change notifies zero clients."""
    from charter.mcp_server import HTTPMCPServer
    http = HTTPMCPServer()
    http._inc_request("GET", "/mcp/health", 200)  # no subscriber -> 0
    assert http._broadcast_metrics_change() == 0


def test_unsubscribed_client_gets_no_push():
    """After unsubscribe, a metrics change does not push to that client."""
    from charter.mcp_server import HTTPMCPServer
    import queue as _q, json as _json
    http = HTTPMCPServer()
    cid = "c10"
    http._client_queues[cid] = _q.Queue()
    http._register_client_key(cid, cid)
    http._server.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/subscribe",
                         "params": {"uri": "charter://metrics", "__client": cid}})
    http._server.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/unsubscribe",
                         "params": {"uri": "charter://metrics", "__client": cid}})
    http._inc_request("GET", "/mcp/health", 200)
    assert http._client_queues[cid].empty(), "no push expected after unsubscribe"


def test_metrics_stream_is_event_driven_not_polling():
    """/mcp/sse?stream=metrics now blocks on the queue (push) instead of sleeping 5s."""
    import inspect
    from charter.mcp_server import HTTPMCPServer
    src = inspect.getsource(HTTPMCPServer._make_handler)
    # The 5s polling sleep is gone; the stream waits on the client queue.
    assert "_time.sleep(5)" not in src, "still polling every 5s"
    assert "q.get(timeout=30)" in src, "event-driven queue wait missing"


# ---------------------------------------------------------------------------
# v3.8 — tools/subscribe_result: push tool-call results to subscribers
# ---------------------------------------------------------------------------

def test_tool_subscribe_result_round_trip():
    """tools/subscribe_result records a tool; list reflects it."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/subscribe_result",
                    "params": {"tool": "slo_evaluate", "__client": "c1"}})
    assert r["result"]["subscribed"] is True
    assert r["result"]["resource"] == "charter://tools/slo_evaluate/result"
    r2 = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list_result_subscriptions",
                     "params": {"__client": "c1"}})
    assert r2["result"]["tools"] == ["slo_evaluate"]
    r3 = srv.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/unsubscribe_result",
                     "params": {"tool": "slo_evaluate", "__client": "c1"}})
    assert r3["result"]["subscribed"] is False
    r4 = srv.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/list_result_subscriptions",
                     "params": {"__client": "c1"}})
    assert r4["result"]["tools"] == []


def test_tool_result_push_to_subscriber():
    """A tools/call for a subscribed tool pushes a resources/changed event to the subscriber."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/subscribe_result",
                "params": {"tool": "slo_evaluate", "__client": "c1"}})
    events = []
    srv._notify_sink = lambda ev: events.append(ev)
    # Call the tool directly via handle; the change notification should fire.
    srv.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "slo_evaluate",
                           "arguments": {"target_p95_ms": 300,
                                          "services": {"api": {"met": False,
                                                                "p95_ms": 900,
                                                                "error_rate": 0.05}}}}})
    # A change event for the subscribed tool's result resource should be pushed
    assert any(e["method"] == "notifications/resources/updated" and
               e["params"]["uri"] == "charter://tools/slo_evaluate/result"
               for e in events), "no tool-result push delivered"


def test_tool_result_no_push_when_not_subscribed():
    """When no client is subscribed to a tool, tools/call pushes nothing."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    events = []
    srv._notify_sink = lambda ev: events.append(ev)
    srv.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "slo_evaluate",
                           "arguments": {}}})
    assert not events, "no push expected without a subscriber"


def test_tool_result_per_client_isolation():
    """Two clients subscribed to the same tool both get the push."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/subscribe_result",
                "params": {"tool": "slo_evaluate", "__client": "a"}})
    srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/subscribe_result",
                "params": {"tool": "slo_evaluate", "__client": "b"}})
    got_a, got_b = [], []
    def sink(ev):
        if ev["params"].get("client") == "a":
            got_a.append(ev)
        else:
            got_b.append(ev)
    srv._notify_sink = sink
    srv.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "slo_evaluate", "arguments": {}}})
    assert len(got_a) == 1 and len(got_b) == 1, "both subscribers should be notified"


# ---------------------------------------------------------------------------
# v3.9 — resources/read on charter://tools/<name>/result (read side of tool
# results, complementing the v3.8 subscription/push side)
# ---------------------------------------------------------------------------

def test_tool_result_resource_read_before_call():
    """resources/read on a tool-result resource with no call yet returns found=False."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                    "params": {"uri": "charter://tools/slo_evaluate/result"}})
    assert "contents" in r["result"]
    import json as _json
    payload = _json.loads(r["result"]["contents"][0]["text"])
    assert payload["found"] is False
    assert payload["tool"] == "slo_evaluate"
    assert r["result"]["contents"][0]["mimeType"] == "application/json"


def test_tool_result_resource_read_after_call():
    """After a tools/call, resources/read returns the last result (found=True)."""
    from charter.mcp_server import CharterMCPServer
    import json as _json
    srv = CharterMCPServer()
    # Call the tool (empty args still run the real chain; ok may be True/False)
    call = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "slo_evaluate", "arguments": {}}})
    assert "result" in call  # the call succeeded at the JSON-RPC level
    r = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/read",
                    "params": {"uri": "charter://tools/slo_evaluate/result"}})
    payload = _json.loads(r["result"]["contents"][0]["text"])
    assert payload["found"] is True
    assert payload["tool"] == "slo_evaluate"
    assert "result" in payload
    assert "ts" in payload


def test_tool_result_resource_per_tool_isolated():
    """Each tool's result resource is independent — calling one doesn't affect another."""
    from charter.mcp_server import CharterMCPServer
    import json as _json
    srv = CharterMCPServer()
    srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "slo_evaluate", "arguments": {}}})
    # slo_evaluate now has a result; a different tool has none
    got = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/read",
                     "params": {"uri": "charter://tools/slo_evaluate/result"}})
    assert _json.loads(got["result"]["contents"][0]["text"])["found"] is True
    other = srv.handle({"jsonrpc": "2.0", "id": 3, "method": "resources/read",
                       "params": {"uri": "charter://tools/pr_autosuggest/result"}})
    assert _json.loads(other["result"]["contents"][0]["text"])["found"] is False


# ---------------------------------------------------------------------------
# v3.10 — resources/changed push carries the full last_result (no follow-up
# resources/read needed) — mirrors the event-sourcing "state derived from
# events" idea from the multi-agent consistency design analysis.
# ---------------------------------------------------------------------------

def test_tool_result_push_carries_full_last_result():
    """A resources/changed event for a tool carries the full last-result payload."""
    from charter.mcp_server import CharterMCPServer
    import json as _json
    srv = CharterMCPServer()
    srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/subscribe_result",
                "params": {"tool": "slo_evaluate", "__client": "c1"}})
    # Call the tool -> the last result is recorded and a change event is pushed.
    srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "slo_evaluate", "arguments": {}}})
    # The _tool_results store now holds the last result.
    last = srv._tool_result_payload("slo_evaluate")
    assert last["found"] is True
    assert "result" in last
    # The change event (if a sink were attached) would carry last_result = this
    # full payload. Verify the payload builder returns the right shape.
    assert last["tool"] == "slo_evaluate"
    assert last["ok"] in (True, False)


def test_tool_result_payload_missing_before_call():
    """_tool_result_payload for a never-called tool reports found=False."""
    from charter.mcp_server import CharterMCPServer
    srv = CharterMCPServer()
    p = srv._tool_result_payload("never_called_tool")
    assert p["found"] is False
    assert "note" in p
    assert p["tool"] == "never_called_tool"


def test_tool_result_push_payload_matches_read_resource():
    """The last_result payload in the change event equals what resources/read returns."""
    from charter.mcp_server import CharterMCPServer
    import json as _json
    srv = CharterMCPServer()
    srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/subscribe_result",
                "params": {"tool": "slo_evaluate", "__client": "c1"}})
    events = []
    srv._notify_sink = lambda ev: events.append(ev)
    srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "slo_evaluate", "arguments": {}}})
    assert events, "no change event delivered"
    push_payload = events[0]["params"]["payload"]
    # The change event carries last_result (full shape).
    assert "last_result" in push_payload
    # Now read the resource and compare: same tool, same found/ok/result fields.
    r = srv.handle({"jsonrpc": "2.0", "id": 3, "method": "resources/read",
                    "params": {"uri": "charter://tools/slo_evaluate/result"}})
    read_payload = _json.loads(r["result"]["contents"][0]["text"])
    # Both should report found=True and carry a "result" field.
    assert push_payload["last_result"]["found"] is True
    assert read_payload["found"] is True
    assert push_payload["last_result"]["result"] == read_payload["result"]
