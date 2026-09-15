"""MCP (Model Context Protocol) server for Charter Orchestrator.

Exposes the 20 governance tools and 47 skills as an MCP server so that
Claude Code, Codex, and any MCP-capable agent harness can mount Charter
as a first-class governance layer.

Protocol: JSON-RPC 2.0 over stdio (MCP 2024-11-05 / 2025-03-26 compatible).
No external dependencies beyond the charter package itself.

Usage:
    # As an MCP server (stdio):
    python -m charter.mcp_server

    # Or in Python:
    from charter.mcp_server import CharterMCPServer
    server = CharterMCPServer()
    result = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
"""
from __future__ import annotations

import json
import sys
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CharterMCPServer",
    "list_mcp_tools",
    "load_skill",
    "run_tool",
    "main", "HTTPMCPServer", "run_http_server",
]

# ---------------------------------------------------------------------------
# Tool registry: the 20 Charter tools mapped to executable handlers
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    # -- Foundation tools (1-6) --
    {
        "name": "init_project",
        "description": "Initialize a Charter-managed project with stage 0 baseline. "
                       "Returns project_id and initial health score.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Unique project identifier"},
                "name": {"type": "string", "description": "Human-readable project name"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "advance_stage",
        "description": "Advance a project to the next stage. Enforces gate checks: "
                       "requires passing TDD + guardrails + evaluation before proceeding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "evidence": {
                    "type": "object",
                    "description": "Stage evidence: {test_results, guardrails_passed, eval_score}",
                },
            },
            "required": ["project_id", "evidence"],
        },
    },
    {
        "name": "confirm_gate",
        "description": "Explicitly confirm a governance gate (human-in-the-loop checkpoint). "
                       "Required before advancing from stage 3 (open-source decision) and stage 8 (delivery).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "gate": {"type": "string", "description": "Gate name (e.g. gate_3, gate_8)"},
                "approver": {"type": "string", "description": "Approver identity"},
            },
            "required": ["project_id", "gate", "approver"],
        },
    },
    {
        "name": "query_status",
        "description": "Query current project status: stage, health, active skills, pending gates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "query_rule",
        "description": "Query a specific governance rule by category. "
                       "Returns the rule text and enforcement level.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Rule category: role_assignment, permission_boundary, "
                                   "communication, tdd, guardrails, autonomous_mode, "
                                   "error_handling, documentation, versioning, "
                                   "security, observability, evaluation, handoff",
                },
                "rule_id": {"type": "string", "description": "Optional specific rule ID"},
            },
            "required": ["category"],
        },
    },
    {
        "name": "list_skills",
        "description": "List all 47 Charter skills by category, with their I/O contracts and "
                       "tool dependencies. Returns manifest data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional filter: env, analysis, dev, test, deploy, collab, tool, security, obs",
                },
            },
        },
    },
    # -- Collaboration & tooling (7-11) --
    {
        "name": "execute_in_sandbox",
        "description": "Execute a shell command in an isolated temp directory with "
                       "security redline filtering (blocks rm -rf /, drop table, API key leaks).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["command"],
        },
    },
    {
        "name": "create_dropbox",
        "description": "Create a handoff dropbox between agents with a message and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dropbox_id": {"type": "string"},
                "message": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["dropbox_id", "message"],
        },
    },
    {
        "name": "manage_task_lifecycle",
        "description": "Manage a task through its lifecycle states (pending -> in_progress -> "
                       "review -> done) with governance audit logging.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "action": {
                    "type": "string",
                    "enum": ["create", "start", "complete", "fail", "status"],
                },
                "details": {"type": "string"},
            },
            "required": ["task_id", "action"],
        },
    },
    {
        "name": "trigger_workflow",
        "description": "Trigger a named workflow (e.g. post_pr_ci, on_failure_retry, "
                       "delivery_checklist) with parameters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["workflow"],
        },
    },
    {
        "name": "create_chat_chain",
        "description": "Create a multi-agent chat chain for collaborative decision-making "
                       "with role-based turn-taking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chain_id": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
                "topic": {"type": "string"},
            },
            "required": ["chain_id", "roles", "topic"],
        },
    },
    # -- Checkpoint & model dispatch (12-14) --
    {
        "name": "save_checkpoint",
        "description": "Save a named checkpoint of project state for later restoration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "restore_checkpoint",
        "description": "Restore project state from a named checkpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "checkpoint_id": {"type": "string"},
            },
            "required": ["project_id", "checkpoint_id"],
        },
    },
    {
        "name": "dispatch_to_model",
        "description": "Route a task to the optimal model based on complexity and type. "
                       "Returns the recommended model and routing rationale.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {
                    "type": "string",
                    "enum": ["coding", "planning", "review", "creative", "math", "general"],
                },
                "complexity": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["task_type"],
        },
    },
    # -- Worktree & TDD (15-16) --
    {
        "name": "manage_worktree",
        "description": "Manage git worktrees for parallel agent development lanes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "worktree_id": {"type": "string"},
                "branch": {"type": "string"},
                "action": {"type": "string", "enum": ["create", "list", "remove", "status"]},
            },
            "required": ["worktree_id", "action"],
        },
    },
    {
        "name": "enforce_tdd",
        "description": "Enforce TDD red-green-refactor discipline. Validates that tests "
                       "were written before implementation and that all tests pass.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "test_results": {
                    "type": "object",
                    "description": "{passed: int, failed: int, skipped: int, evidence: str}",
                },
            },
            "required": ["test_results"],
        },
    },
    # -- Guardrails & autonomous (17-18) --
    {
        "name": "guardrails",
        "description": "Run the guardrails engine: validate input payload against "
                       "security redlines and output filtering rules.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["validate_input", "filter_output", "audit"]},
                "payload": {"type": "object"},
            },
            "required": ["action", "payload"],
        },
    },
    {
        "name": "enable_autonomous_mode",
        "description": "Enable or disable autonomous operation for a specific scope. "
                       "In autonomous mode, gates are auto-confirmed with audit logging.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "enabled": {"type": "boolean"},
                "scope": {
                    "type": "string",
                    "description": "autonomous scope: all, dev, test, deploy, or a stage name",
                },
            },
            "required": ["project_id", "enabled"],
        },
    },
    # -- Tracing (19-20) --
    {
        "name": "trace_operation",
        "description": "Record a trace span for an operation with attributes. "
                       "Returns the trace_id for later querying.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "attributes": {"type": "object"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "query_trace",
        "description": "Query recorded traces by trace_id or list recent operations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "trace_id": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def run_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Charter tool by name. Returns {ok, result, error}."""
    try:
        from charter import core, governance, tools, observability, evaluation

        if tool_name == "init_project":
            pid = args.get("project_id", "default")
            project_type = args.get("project_type", "dev")
            objective = args.get("objective", f"governed project {pid}")
            out = core.init_project(pid, project_type, objective)
            return {"ok": True, "result": out}

        elif tool_name == "advance_stage":
            pid = args["project_id"]
            evidence = args.get("evidence", {})
            return {"ok": True, "result": core.advance_stage(pid, evidence=evidence)}

        elif tool_name == "confirm_gate":
            pid = args["project_id"]
            gate = args.get("gate", "gate")
            approver = args.get("approver", "anonymous")
            gate_type = args.get("gate_type", "stage_gate")
            evidence = args.get("evidence", {"confirmed_by": approver})
            return {"ok": True, "result": core.confirm_gate(pid, gate, gate_type, evidence)}

        elif tool_name == "query_status":
            pid = args["project_id"]
            return {"ok": True, "result": core.query_status(pid)}

        elif tool_name == "query_rule":
            category = args.get("category", "")
            rule_id = args.get("rule_id")
            from charter.governance import RULES
            matches = [r for r in RULES if r.get("category") == category]
            if rule_id:
                matches = [r for r in matches if r.get("id") == rule_id]
            return {"ok": True, "result": {"rules": matches, "count": len(matches)}}

        elif tool_name == "list_skills":
            import json as _json
            manifest_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "skills", "manifest.json")
            with open(manifest_path, encoding="utf-8") as f:
                manifest = _json.load(f)
            skills = manifest.get("skills", {})
            category = args.get("category")
            if category:
                skills = {k: v for k, v in skills.items() if v.get("category") == category}
            return {"ok": True, "result": {
                "total": len(skills),
                "tools": manifest.get("tools", []),
                "skills": skills,
            }}

        elif tool_name == "execute_in_sandbox":
            return {"ok": True, "result": tools.execute_in_sandbox(
                args["command"], args.get("timeout", 60))}

        elif tool_name == "create_dropbox":
            return {"ok": True, "result": tools.create_dropbox(
                args["dropbox_id"], args["message"], args.get("metadata", {}))}

        elif tool_name == "manage_task_lifecycle":
            return {"ok": True, "result": tools.manage_task_lifecycle(
                args["task_id"], args["action"], args.get("details", ""))}

        elif tool_name == "trigger_workflow":
            return {"ok": True, "result": tools.trigger_workflow(
                args["workflow"], args.get("params", {}))}

        elif tool_name == "create_chat_chain":
            return {"ok": True, "result": tools.create_chat_chain(
                args["chain_id"], args["roles"], args["topic"])}

        elif tool_name == "save_checkpoint":
            return {"ok": True, "result": core.save_checkpoint(
                args["project_id"], args.get("label", ""))}

        elif tool_name == "restore_checkpoint":
            return {"ok": True, "result": core.restore_checkpoint(
                args["project_id"], args["checkpoint_id"])}

        elif tool_name == "dispatch_to_model":
            task_type = args.get("task_type", "general")
            complexity = args.get("complexity", 0.5)
            routing = {
                "coding": "agnes-2.5-flash" if complexity < 0.7 else "agnes-3.0",
                "planning": "agnes-3.0",
                "review": "agnes-2.5-flash",
                "creative": "agnes-3.0",
                "math": "agnes-3.0",
                "general": "agnes-2.5-flash" if complexity < 0.5 else "agnes-3.0",
            }
            model = routing.get(task_type, "agnes-2.5-flash")
            return {"ok": True, "result": {
                "recommended_model": model,
                "task_type": task_type,
                "complexity": complexity,
                "rationale": f"complexity={complexity:.1f} -> {model}",
            }}

        elif tool_name == "manage_worktree":
            worktree_id = args["worktree_id"]
            action = args.get("action", "status")
            import subprocess
            if action == "create":
                branch = args.get("branch", f"charter/{worktree_id}")
                r = subprocess.run(
                    ["git", "worktree", "add", f".charter-wt-{worktree_id}",
                     "-b", branch],
                    capture_output=True, text=True, timeout=30)
                return {"ok": r.returncode == 0,
                        "result": {"worktree": f".charter-wt-{worktree_id}",
                                   "branch": branch,
                                   "raw": r.stdout + r.stderr}}
            elif action == "list":
                r = subprocess.run(
                    ["git", "worktree", "list"],
                    capture_output=True, text=True, timeout=10)
                return {"ok": True, "result": {"worktrees": r.stdout.strip()}}
            elif action == "remove":
                r = subprocess.run(
                    ["git", "worktree", "remove", f".charter-wt-{worktree_id}"],
                    capture_output=True, text=True, timeout=30)
                return {"ok": r.returncode == 0,
                        "result": {"raw": r.stdout + r.stderr}}
            else:
                return {"ok": True, "result": {"status": "unknown action", "action": action}}

        elif tool_name == "enforce_tdd":
            from charter.governance import TDDEnforcer
            enforcer = TDDEnforcer()
            result = enforcer.check_red_green(args.get("test_results"))
            # "pass" and "warning" are both acceptable outcomes; only "fail" is a hard stop
            ok = result.get("status") in ("pass", "warning")
            return {"ok": ok, "result": result}

        elif tool_name == "guardrails":
            action = args["action"]
            payload = args.get("payload", {})
            if action == "validate_input":
                from charter.governance import GuardrailsEngine
                engine = GuardrailsEngine()
                return {"ok": True, "result": engine.validate_input(payload)}
            elif action == "filter_output":
                from charter.governance import GuardrailsEngine
                engine = GuardrailsEngine()
                return {"ok": True, "result": engine.filter_outputs(payload)}
            else:  # audit
                from charter.governance import GuardrailsEngine
                engine = GuardrailsEngine()
                return {"ok": True, "result": engine.audit(payload)}

        elif tool_name == "enable_autonomous_mode":
            pid = args["project_id"]
            enabled = args.get("enabled", False)
            scope = args.get("scope", "all")
            project = core._get(pid)
            project.autonomous_mode = enabled
            project.autonomous_scope = scope
            return {"ok": True, "result": {
                "project_id": pid,
                "autonomous_mode": enabled,
                "scope": scope,
                "note": "gates auto-confirmed in autonomous scope; audit trail preserved",
            }}

        elif tool_name == "trace_operation":
            return {"ok": True, "result": observability.trace_operation(
                args["name"], args.get("attributes"))}

        elif tool_name == "query_trace":
            return {"ok": True, "result": observability.query_trace(
                args.get("trace_id"), args.get("limit", 20))}

        else:
            return {"ok": False, "error": f"unknown tool: {tool_name}"}

    except Exception as e:
        import traceback
        return {"ok": False, "error": str(e), "traceback": traceback.format_exc()}


# ---------------------------------------------------------------------------
# Skill loading
# ---------------------------------------------------------------------------

def load_skill(skill_id: str) -> Dict[str, Any]:
    """Load a skill by ID (e.g. 'analysis_01'). Returns its manifest entry
    and the full SKILL.md content."""
    import json as _json
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base, "skills", "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = _json.load(f)
    entry = manifest.get("skills", {}).get(skill_id)
    if entry is None:
        return {"found": False, "skill_id": skill_id,
                "error": f"skill '{skill_id}' not in manifest"}
    skill_md_path = os.path.join(base, entry.get("path", ""))
    skill_md = ""
    if os.path.isfile(skill_md_path):
        with open(skill_md_path, encoding="utf-8") as f:
            skill_md = f.read()
    return {
        "found": True,
        "skill_id": skill_id,
        "manifest": entry,
        "content": skill_md,
    }


# ---------------------------------------------------------------------------
# MCP server (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

MCP_SERVER_INFO = {
    "name": "charter-orchestrator",
    "version": "3.2.0",
    "description": "Full-lifecycle governance & orchestration framework for AI agents. "
                   "Exposes 20 governance tools and 47 structured skills with "
                   "enforceable gates, TDD, guardrails, and human-confirmation points.",
}


def list_mcp_tools() -> List[Dict[str, Any]]:
    """Return the MCP tool definitions (all 20 Charter tools)."""
    return TOOL_DEFINITIONS


class CharterMCPServer:
    """MCP server implementing JSON-RPC 2.0 over stdio.

    Supports:
      - initialize
      - tools/list
      - tools/call
      - resources/list  (47 skills as resources)
      - resources/read  (skill content by ID)
      - ping
    """

    def __init__(self) -> None:
        self._initialized = False
        self._resource_list: List[Dict[str, Any]] = []
        self._build_resources()
        # v3.6: resource subscriptions + live metrics resource
        import threading as _th
        self._subs_lock = _th.Lock()
        self._subscriptions: Dict[str, set] = {}
        # Optional reference to the HTTPMCPServer that owns this instance,
        # set when constructed by HTTPMCPServer, so the metrics resource
        # can expose live request counters.
        self._http_owner: Optional[Any] = None
        # v3.7: push-style change notifications (MCP notifications/resources/updated).
        # An optional sink callable the HTTP owner sets: fn(event_dict) -> None,
        # invoked for each client that is subscribed to a changed resource.
        self._notify_sink: Optional[Any] = None
        # v3.8: per-client tool-result subscriptions. When a client subscribes to
        # "tool results" for a given tool name, every subsequent tools/call for
        # that tool triggers a resources/changed push to that client (the tool's
        # output is exposed as the virtual resource charter://tools/<name>/result).
        self._tool_subscriptions: Dict[str, set] = {}  # client_key -> set of tool names

    def _build_resources(self) -> None:
        import json as _json
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        manifest_path = os.path.join(base, "skills", "manifest.json")
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = _json.load(f)
            for sid, meta in manifest.get("skills", {}).items():
                self._resource_list.append({
                    "uri": f"charter://skills/{sid}",
                    "name": meta.get("name", sid),
                    "description": f"Charter skill: {meta.get('name', sid)} "
                                    f"({meta.get('category', '?')}) — "
                                    f"tools: {', '.join(meta.get('tools', []))}",
                    "mimeType": "text/markdown",
                })
        except Exception:
            pass
        # v3.6: always expose the live metrics resource (outside the try so it
        # is registered even when the manifest is missing/unreadable).
        self._resource_list.append({
            "uri": "charter://metrics",
            "name": "charter-metrics",
            "description": "Live Prometheus-format request counters for the "
                           "Charter MCP HTTP+SSE server. Subscribe to be "
                           "notified when counters change.",
            "mimeType": "text/plain; version=0.0.4",
        })

    def _metrics_resource_text(self) -> str:
        """Text payload for the ``charter://metrics`` resource.

        When this instance is owned by an :class:`HTTPMCPServer` (HTTP+SSE
        mode), the owner's live request counters are exposed. In stdio mode
        there are no HTTP counters, so a static explanatory note is returned.
        """
        owner = self._http_owner
        if owner is not None and hasattr(owner, "_metrics_payload"):
            try:
                return owner._metrics_payload()["text"]
            except Exception:
                pass
        return (
            "# Charter MCP metrics resource (charter://metrics)\n"
            "# stdio mode: no HTTP request counters available.\n"
            "# Use the HTTP+SSE transport (run_http_server) and the\n"
            "# /metrics endpoint for Prometheus-format counters.\n"
        )

    def notify_resource_changed(self, uri: str, client_key: str,
                                payload: Optional[Dict[str, Any]] = None) -> bool:
        """Push an MCP ``notifications/resources/updated`` event to one client.

        Returns True when the client had an open subscription to ``uri`` (the
        event was queued for delivery); False otherwise. When an HTTP owner
        attached a ``_notify_sink``, that sink is invoked with a JSON-RPC
        notification dict so the SSE transport can deliver it.
        """
        subscribed = False
        with self._subs_lock:
            subs = self._subscriptions.get(client_key, set())
            subscribed = uri in subs
            if not subscribed:
                return False
        event = {
            "jsonrpc": "2.0",
            "method": "notifications/resources/updated",
            "params": {
                "uri": uri,
                "client": client_key,
                "payload": payload or {},
                "ts": __import__("time").time(),
            },
        }
        sink = self._notify_sink
        if sink is not None:
            try:
                sink(event)
            except Exception:
                pass
        return True

    def _notify_tool_result_changed(self, tool_name: str,
                                    outcome: Dict[str, Any]) -> int:
        """v3.8: push a resources/changed event to every client subscribed to
        ``tool_name``'s result resource. Returns the number of clients notified."""
        with self._subs_lock:
            keys = [k for k, tools in self._tool_subscriptions.items()
                    if tool_name in tools]
        resource_uri = f"charter://tools/{tool_name}/result"
        notified = 0
        for key in keys:
            payload = {"tool": tool_name, "result": outcome,
                       "ok": outcome.get("ok", False)}
            if self.notify_resource_changed(resource_uri, key, payload=payload):
                notified += 1
        return notified

    # -- JSON-RPC dispatch ------------------------------------------------

    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            self._initialized = True
            return self._result(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": True, "listChanged": False},
                },
                "serverInfo": MCP_SERVER_INFO,
            })

        if method == "tools/list":
            return self._result(msg_id, {"tools": list_mcp_tools()})

        if method == "tools/call":
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            outcome = run_tool(tool_name, args)
            text = json.dumps(outcome, ensure_ascii=False, default=str)
            # v3.8: push the tool-result change to any client subscribed to this
            # tool's result resource (charter://tools/<name>/result).
            self._notify_tool_result_changed(tool_name, outcome)
            return self._result(msg_id, {
                "content": [{"type": "text", "text": text}],
                "isError": not outcome.get("ok", False),
            })

        if method == "resources/list":
            return self._result(msg_id, {"resources": self._resource_list})

        if method == "resources/read":
            uri = params.get("uri", "")
            if uri == "charter://metrics":
                # Live metrics resource: return the HTTP server's counters
                # when running over HTTP+SSE, otherwise a static note.
                metrics_text = self._metrics_resource_text()
                return self._result(msg_id, {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "text/plain; version=0.0.4",
                        "text": metrics_text,
                    }]
                })
            if not uri.startswith("charter://skills/"):
                return self._error(msg_id, -32602, f"unsupported URI: {uri}")
            skill_id = uri.split("/")[-1]
            entry = load_skill(skill_id)
            if not entry.get("found"):
                return self._error(msg_id, -32602, entry.get("error", "skill not found"))
            return self._result(msg_id, {
                "contents": [{
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": entry.get("content", ""),
                }]
            })

        # --- resource subscriptions (v3.6) ---
        if method == "resources/subscribe":
            uri = params.get("uri", "")
            client_key = params.get("__client", "_stdio")
            with self._subs_lock:
                self._subscriptions.setdefault(client_key, set()).add(uri)
            return self._result(msg_id, {"uri": uri, "subscribed": True,
                                          "client": client_key})

        if method == "resources/unsubscribe":
            uri = params.get("uri", "")
            client_key = params.get("__client", "_stdio")
            with self._subs_lock:
                self._subscriptions.get(client_key, set()).discard(uri)
            return self._result(msg_id, {"uri": uri, "subscribed": False,
                                          "client": client_key})

        if method == "resources/list_subscriptions":
            client_key = params.get("__client", "_stdio")
            with self._subs_lock:
                subs = sorted(self._subscriptions.get(client_key, set()))
            return self._result(msg_id, {"client": client_key,
                                          "subscriptions": subs})

        # v3.8: subscribe to a tool's result resource.
        if method == "tools/subscribe_result":
            tool_name = params.get("tool", "")
            client_key = params.get("__client", "_stdio")
            resource_uri = f"charter://tools/{tool_name}/result"
            with self._subs_lock:
                self._tool_subscriptions.setdefault(client_key, set()).add(tool_name)
                # Also record in the generic resource-subscription set so the
                # notify_resource_changed gate (which checks _subscriptions)
                # lets the push through for this client.
                self._subscriptions.setdefault(client_key, set()).add(resource_uri)
            return self._result(msg_id, {"tool": tool_name, "subscribed": True,
                                          "resource": resource_uri,
                                          "client": client_key})

        if method == "tools/unsubscribe_result":
            tool_name = params.get("tool", "")
            client_key = params.get("__client", "_stdio")
            resource_uri = f"charter://tools/{tool_name}/result"
            with self._subs_lock:
                self._tool_subscriptions.get(client_key, set()).discard(tool_name)
                self._subscriptions.get(client_key, set()).discard(resource_uri)
            return self._result(msg_id, {"tool": tool_name, "subscribed": False,
                                          "client": client_key})

        if method == "tools/list_result_subscriptions":
            client_key = params.get("__client", "_stdio")
            with self._subs_lock:
                tools = sorted(self._tool_subscriptions.get(client_key, set()))
            return self._result(msg_id, {"client": client_key, "tools": tools})

        if method == "ping":
            if msg_id is None:
                return None  # notification: no response
            return self._result(msg_id, {})

        if msg_id is None:
            # unknown notification — no response
            return None

        return self._error(msg_id, -32601, f"method not found: {method}")

    @staticmethod
    def _result(id_: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": id_, "result": result}

    @staticmethod
    def _error(id_: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def main() -> None:
    """Run the MCP server over stdio."""
    server = CharterMCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = CharterMCPServer._error(None, -32700, "parse error")
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
            continue
        resp = server.handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()



# ---------------------------------------------------------------------------
# SSE / HTTP transport (optional, for remote MCP clients)
# ---------------------------------------------------------------------------
#
# The stdio transport is the default (zero-dependency). For remote mounting
# (Claude Desktop web, Codex remote, or a network-attached agent harness),
# an optional HTTP + SSE transport is provided using ONLY the stdlib
# ``http.server`` module — no ``mcp`` SDK, no ``fastapi``/``aiohttp``.
#
#   from charter.mcp_server import run_http_server
#   run_http_server(host="127.0.0.1", port=8765)
#
# Endpoints (JSON-RPC 2.0, same semantics as the stdio server):
#   GET  /mcp/sse          - SSE stream: emits the initial "endpoint" event
#                            carrying the POST URL, then relays server->client
#                            notifications (ping / tool progress).
#   POST /mcp/message      - JSON-RPC request body; the JSON-RPC response is
#                            pushed back over the SSE stream (event "message").
#   GET  /mcp/health       - liveness probe (200 + server info).
#   GET  /mcp/tools        - convenience: returns the 20 tool definitions.
#
# The transport is process-local: one CharterMCPServer instance backs all
# connections; a thread-safe queue bridges POST responses to the SSE stream.

import threading
import queue
import http.server
import socketserver


class HTTPMCPServer:
    """HTTP + SSE wrapper around a :class:`CharterMCPServer`."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765,
                 api_key: Optional[str] = None) -> None:
        self.host = host
        self.port = port
        # Auth: an API key gates every /mcp/* endpoint. If none is passed,
        # fall back to the CHARTER_MCP_API_KEY env var. When the key is empty/
        # unset, the server runs open (backwards-compatible with v3.2).
        self.api_key = api_key if api_key is not None else os.environ.get("CHARTER_MCP_API_KEY")
        self._server = CharterMCPServer()
        self._server._http_owner = self  # v3.6: expose live metrics via the resource
        self._lock = threading.Lock()
        # v3.7: map subscription client_key -> SSE client id (cid) so push
        # notifications can be routed to the right per-client queue.
        self._client_keys: Dict[str, str] = {}
        self._client_keys_lock = threading.Lock()
        # v3.7: register a notification sink on the inner MCP server so
        # resources/changed events are pushed onto the subscriber's SSE queue.
        self._server._notify_sink = self._push_notification
        # Per-client SSE queues keyed by a client id.
        self._client_queues: Dict[str, "queue.Queue"] = {}
        self._clients_lock = threading.Lock()
        self._next_client = 0
        # Prometheus-style request counters (v3.5 /metrics endpoint).
        self._metrics_lock = threading.Lock()
        self._request_total: Dict[tuple, int] = {}
        self._label_counters: Dict[str, int] = {}
        self._request_started = __import__("time").time()

    # -- metrics helpers ----------------------------------------------------
    def _inc_request(self, method: str, endpoint: str, status_code: int) -> None:
        status_class = f"{status_code // 100}xx"
        key = (method, endpoint, status_class)
        with self._metrics_lock:
            self._request_total[key] = self._request_total.get(key, 0) + 1
            self._label_counters[endpoint] = self._label_counters.get(endpoint, 0) + 1
        # v3.7: push a resources/changed notification to any client subscribed
        # to charter://metrics, so dashboards update without polling.
        try:
            self._broadcast_metrics_change()
        except Exception:
            pass

    def _metrics_payload(self) -> Dict[str, Any]:
        with self._metrics_lock:
            total = dict(self._request_total)
            by_endpoint = dict(self._label_counters)
        uptime = __import__("time").time() - self._request_started
        lines = [
            "# HELP charter_mcp_requests_total Total MCP HTTP requests, by method/endpoint/status.",
            "# TYPE charter_mcp_requests_total counter",
        ]
        for (method, endpoint, status_class), count in sorted(total.items()):
            lines.append(
                f'charter_mcp_requests_total{{method="{method}",endpoint="{endpoint}",status="{status_class}"}} {count}')
        lines += [
            "# HELP charter_mcp_requests_by_endpoint_total Total MCP HTTP requests, by endpoint.",
            "# TYPE charter_mcp_requests_by_endpoint_total counter",
        ]
        for endpoint, count in sorted(by_endpoint.items()):
            lines.append(f'charter_mcp_requests_by_endpoint_total{{endpoint="{endpoint}"}} {count}')
        lines += [
            "# HELP charter_mcp_uptime_seconds Seconds since the MCP HTTP server started.",
            "# TYPE charter_mcp_uptime_seconds gauge",
            f"charter_mcp_uptime_seconds {uptime:.3f}",
        ]
        return {"text": "\n".join(lines) + "\n"}

    def _handle_metrics(self) -> None:
        payload = self._metrics_payload()
        body = payload["text"].encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self, request_headers: Any) -> bool:
        """True when the request is allowed under the current auth policy.

        - no api_key configured  -> always allowed (open server)
        - api_key configured     -> requires a matching ``X-API-Key`` header
        """
        if not self.api_key:
            return True
        provided = None
        get_header = getattr(request_headers, "get", None)
        if callable(get_header):
            provided = get_header("X-API-Key")
        if provided is None and isinstance(request_headers, dict):
            provided = request_headers.get("X-API-Key")
        # constant-time-ish compare to avoid timing leaks on the prefix
        import hmac
        return hmac.compare_digest(provided or "", self.api_key)

    # -- client registration ------------------------------------------------
    def _new_client(self) -> str:
        with self._clients_lock:
            self._next_client += 1
            cid = f"c{self._next_client}"
            self._client_queues[cid] = queue.Queue()
            return cid

    def _drop_client(self, cid: str) -> None:
        with self._clients_lock:
            self._client_queues.pop(cid, None)
        # v3.7: clean up the client-key mapping if this cid was its own key.
        self._drop_client_key(cid)

    def _register_client_key(self, cid: str, key: str) -> None:
        """v3.7: link an SSE client id to its subscription key."""
        with self._client_keys_lock:
            self._client_keys[key] = cid

    def _drop_client_key(self, key: str) -> None:
        with self._client_keys_lock:
            self._client_keys.pop(key, None)

    def _push_notification(self, event: Dict[str, Any]) -> None:
        """v3.7: deliver a resources/changed event to the subscriber's SSE queue.

        The event carries the client key; route it to that client's per-client
        queue (SSE `event: message`). Unknown clients are dropped silently.
        """
        client_key = event.get("params", {}).get("client", "")
        cid: Optional[str] = None
        with self._client_keys_lock:
            cid = self._client_keys.get(client_key)
        if cid is None:
            return
        q = self._client_queues.get(cid)
        if q is None:
            return
        import json as _json
        q.put(_json.dumps(event, ensure_ascii=False))

    def _broadcast_metrics_change(self) -> int:
        """v3.7: push a metrics change notification to every client subscribed
        to ``charter://metrics``. Returns the number of clients notified.

        Called from ``_inc_request`` so subscribed dashboards get a push
        instead of polling every 5s.
        """
        inner = self._server
        with inner._subs_lock:
            subscribed_keys = [
                key for key, subs in inner._subscriptions.items()
                if "charter://metrics" in subs
            ]
        snap = self._metrics_payload()["text"]
        notified = 0
        for key in subscribed_keys:
            if inner.notify_resource_changed("charter://metrics", key,
                                              payload={"metrics": snap}):
                notified += 1
        return notified

    # -- HTTP handler --------------------------------------------------------
    def _make_handler(self):
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence default stderr logging
                return

            def _send_json(self, code: int, obj: Any) -> None:
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _auth_deny(self) -> None:
                self._send_json(401, {"error": "unauthorized",
                                      "hint": "send an X-API-Key header matching CHARTER_MCP_API_KEY"})

            def do_GET(self):
                if self.path == "/metrics":
                    outer._inc_request("GET", "/metrics", 200)
                    outer._handle_metrics()
                    return
                if not outer._auth_ok(self.headers):
                    outer._inc_request("GET", self.path, 401)
                    self._auth_deny()
                    return
                if self.path == "/mcp/health":
                    outer._inc_request("GET", "/mcp/health", 200)
                    self._send_json(200, {"ok": True, "server": MCP_SERVER_INFO,
                                          "auth_required": bool(outer.api_key)})
                elif self.path == "/mcp/tools":
                    outer._inc_request("GET", "/mcp/tools", 200)
                    self._send_json(200, {"tools": list_mcp_tools()})
                elif self.path == "/mcp/sse":
                    outer._inc_request("GET", "/mcp/sse", 200)
                    self._sse_stream()
                else:
                    outer._inc_request("GET", self.path, 404)
                    self._send_json(404, {"error": "not found"})

            def do_POST(self):
                if not outer._auth_ok(self.headers):
                    outer._inc_request("POST", self.path, 401)
                    self._auth_deny()
                    return
                if self.path == "/mcp/message":
                    outer._inc_request("POST", "/mcp/message", 202)
                    self._handle_message()
                else:
                    outer._inc_request("POST", self.path, 404)
                    self._send_json(404, {"error": "not found"})

            def _sse_stream(self):
                from urllib.parse import urlparse, parse_qs as _pq
                _q = _pq(urlparse(self.path).query)
                stream_mode = (_q.get("stream") or ["mcp"])[0]  # "mcp" | "metrics"
                cid = outer._new_client()
                # v3.7: the SSE client may subscribe to resources using its
                # cid as the __client key; register that mapping so push
                # notifications (resources/changed) are routed here.
                outer._register_client_key(cid, cid)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                # initial event: tell the client where to POST
                post_url = f"/mcp/message?client={cid}"
                self.wfile.write(f"event: endpoint\ndata: {post_url}\n\n".encode())
                self.wfile.flush()
                q = outer._client_queues[cid]
                try:
                    if stream_mode == "metrics":
                        # v3.7: event-driven. Emit an initial snapshot, then
                        # block on the per-client queue for resources/changed
                        # push events (or a keepalive timeout). Each push
                        # carries the fresh metrics text in the event payload;
                        # when one arrives, re-send it. This replaces the
                        # previous 5s polling loop.
                        import time as _time
                        # initial snapshot so a fresh subscriber has data
                        snap = outer._metrics_payload()["text"]
                        data_lines = "".join(
                            f"data: {line}\n" for line in snap.splitlines())
                        self.wfile.write(f"event: metrics\n{data_lines}\n".encode())
                        self.wfile.flush()
                        while True:
                            try:
                                item = q.get(timeout=30)
                            except queue.Empty:
                                # keepalive comment so proxies don't time out
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                                continue
                            if item is None:
                                break
                            # item is a JSON-RPC notification (resources/changed)
                            # carrying the fresh metrics snapshot.
                            import json as _json
                            try:
                                evt = _json.loads(item)
                                new_snap = (evt.get("params") or {}).get("payload", {}).get("metrics")
                            except Exception:
                                new_snap = None
                            if new_snap is None:
                                new_snap = outer._metrics_payload()["text"]
                            data_lines = "".join(
                                f"data: {line}\n" for line in new_snap.splitlines())
                            self.wfile.write(f"event: metrics\n{data_lines}\n".encode())
                            self.wfile.flush()
                    else:
                        while True:
                            try:
                                item = q.get(timeout=15)
                            except queue.Empty:
                                # keepalive comment so proxies don't time out
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                                continue
                            if item is None:
                                break
                            self.wfile.write(
                                f"event: message\ndata: {item}\n\n".encode())
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    outer._drop_client(cid)

            def _handle_message(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    msg = json.loads(raw.decode("utf-8"))
                except Exception:
                    resp = CharterMCPServer._error(None, -32700, "parse error")
                    self._send_json(400, resp)
                    return
                # parse the client id from the query string
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                cid = (q.get("client") or ["default"])[0]
                resp = outer._server.handle(msg)
                if resp is None:
                    self.send_response(202)  # accepted, no response (notification)
                    self.end_headers()
                    return
                if cid in outer._client_queues:
                    outer._client_queues[cid].put(json.dumps(resp, ensure_ascii=False))
                self.send_response(202)  # accepted; result delivered via SSE
                self.end_headers()

        return Handler

    def run(self) -> None:
        handler = self._make_handler()

        class ThreadingServer(socketserver.ThreadingMixIn,
                              http.server.HTTPServer):
            daemon_threads = True

        ThreadingServer.allow_reuse_address = True
        httpd = ThreadingServer((self.host, self.port), handler)
        print(f"Charter MCP HTTP+SSE server on http://{self.host}:{self.port}/mcp/sse")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()


def run_http_server(host: str = "127.0.0.1", port: int = 8765,
                    api_key: Optional[str] = None) -> None:
    """Start the optional HTTP + SSE MCP transport (stdlib-only).

    Auth: pass ``api_key`` or set the ``CHARTER_MCP_API_KEY`` env var to gate
    all ``/mcp/*`` endpoints behind an ``X-API-Key`` header. When neither is
    set the server stays open (default, matches v3.2 behaviour).
    """
    if api_key is None:
        api_key = os.environ.get("CHARTER_MCP_API_KEY")
    HTTPMCPServer(host=host, port=port, api_key=api_key).run()


if __name__ == "__main__":
    main()