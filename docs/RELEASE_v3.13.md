# v3.13.0 - Governance MCP tools + Critic repair-rerun + distributed SemanticCache + demo --gov

## New features

### 1. Four governance MCP tools (20 -> 24)
| tool | module | purpose |
|---|---|---|
| `validate_output` | `validation_gateway` | Field contract check (schema + data-alignment + consistency) |
| `critic_plan` | `critic_agent` | Plan DAG audit; optional `closed_loop` repair-and-recheck |
| `trace_span` | `semantic_trace` | Input->output semantic drift + hallucination verdict |
| `route_task` | `model_router` | Model tier routing; optional `SemanticCache` write |

Skills `gov_05`..`gov_08` added (manifest 115 skills, 24 tools).

### 2. Critic repair-rerun agent closed loop
`charter.critic_agent.repair_and_rerun(plan, executor, max_rounds)` - full
reflect -> repair -> agent re-execute -> re-audit loop. `executor(step)`
drives per-step reruns; executor exceptions are recorded, never propagated.
No-executor mode degrades to `reflect_until_sound` (plan-only).

### 3. Distributed SemanticCache (pluggable remote L3)
`SemanticCache(semantic_key, max_entries, disk_path, remote)` - three-level
L1 memory -> L2 SQLite -> L3 remote. `HTTPKeyValueBackend` (stdlib-only,
offline-safe: network errors degrade to miss) + `make_remote_backend(kind,
base_url)` factory (`http`/`kv`/`redis`/`postgres`/`memcached`/`null`).
`stats()` exposes `remote_enabled`/`remote`.

### 4. `charter.cli demo --gov`
End-to-end governance demo: 4-module chain + closed-loop + repair-and-rerun.

## Tests
492 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_gov_mcp_tools.py`,
`tests/test_critic_repair_rerun.py`, `tests/test_semantic_cache_remote.py`,
`tests/test_v3_13.py` (CLI check).

## Quickstart
```python
from charter import (ValidationGateway, CriticPlan, CriticStep,
                     repair_and_rerun, SemanticCache, make_remote_backend,
                     TaskProfile, ModelRouter)

# 1) MCP governance tools
from charter.mcp_server import list_mcp_tools, run_tool
assert len(list_mcp_tools()) == 24
r = run_tool("critic_plan", {"plan": {...}, "closed_loop": True})

# 2) Repair-rerun agent loop
plan = CriticPlan(plan_id="p", goal="g", steps=[CriticStep(id="a"), CriticStep(id="b")])
report = repair_and_rerun(plan, executor=lambda s: {"done": True}, max_rounds=3)

# 3) Distributed cache
remote = make_remote_backend("redis", "http://kv-gateway:8080")
cache = SemanticCache(disk_path="/tmp/sc.db", remote=remote)
cache.put("q1", 42); cache.close()

# 4) CLI
python -m charter.cli demo --gov
```
