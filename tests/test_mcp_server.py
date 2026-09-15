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


def test_version_is_v3_4():
    assert __version__.startswith("3.4")


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
    assert out["result"]["total"] == 107, f"expected 47 skills, got {out['result']['total']}"


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
    assert len(resources) == 107, f"expected 107 skill resources, got {len(resources)}"
    for res in resources:
        assert res["uri"].startswith("charter://skills/")
        assert res["mimeType"] == "text/markdown"


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
    # It wraps a CharterMCPServer and builds 107 resources
    assert hasattr(srv, "_server")
    resources = srv._server._resource_list
    assert len(resources) == 107, f"expected 107 resources, got {len(resources)}"
    # all URIs are well-formed
    for r in resources:
        assert r["uri"].startswith("charter://skills/")


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
    """All 107 manifest entries point to a file that exists on disk."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base, "skills", "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    skills = manifest["skills"]
    assert len(skills) == 107
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
