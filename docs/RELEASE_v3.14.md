# v3.14.0 - Plan pipeline + self-healing agent loop + L3 consistency + live demo

## New features

### 1. `plan_pipeline` MCP tool (25 total)
Plan-to-routing pipeline in one call: run the Critic on a task-plan DAG
(optional `closed_loop` repair-and-recheck), then route every step of the
final plan to its optimal model tier via the ModelRouter. Step depth is
computed from the DAG's transitive ancestors; `depth_scale` / `default_risk` /
`default_tokens` shape the TaskProfile. Returns `{critic, final_plan, routing}`.

### 2. Self-healing agent loop (`executor="mcp"`)
`repair_and_rerun(plan, executor="mcp")` now binds the default agent hook to
`charter.mcp_server.run_tool`: each repaired step whose `name` is an MCP tool
is re-executed through the real tool dispatch before the next post-audit.
Full "critic -> repair -> re-run the actual tool -> re-audit" loop.
`mcp_step_executor()` is exported from `charter`.

### 3. L3 distributed consistency (version stamp + TTL + optimistic lock)
- `SemanticCache(ttl_s=...)` - per-key time-to-live; expired L3 entries are
  treated as misses on read.
- Remote writes are version-stamped: the payload is wrapped in
  `{"__v": int, "__ts": float, "value": ...}`; `get_version(request)`
  returns the last-written version (optimistic-lock token), reading the
  local tracking table or querying the remote backend on first contact.
- `HTTPKeyValueBackend.put_if_version(key, value, if_version)` -
  optimistic write via the `X-If-Version` header; a conforming gateway
  returns 409 on mismatch, which degrades to `False` (offline-safe).
- `stats()` now exposes `ttl_s` + `remote_versions`.

### 4. `charter.cli demo --gov --live`
Spins up a real in-process HTTP KV gateway and demonstrates a
cross-process L3 hit: node 1 writes a versioned value, node 2 (fresh
memory) reads it back via L3 with the version visible.

## Tests
502 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_14.py`
(plan_pipeline 4, mcp executor 2, L3 consistency 4).
