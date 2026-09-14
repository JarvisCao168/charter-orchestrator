# v2.0 Production Layers / v2.0 生产层

Four modules close the gaps flagged in the 2026 peer review (Red Hat "7 missing
production capabilities", Microsoft agent-eval, MAST fault taxonomy).

## 1. OpenTelemetry + Grafana / 可观测性导出 — `charter/otel_export.py`

```python
from charter import export_project
from charter.core import _REGISTRY

p = _REGISTRY[pid]
otlp = export_project(p.trace, fmt="otlp")        # -> OTLP/JSON resourceSpans
prom = export_project(p.trace, pid, fmt="prometheus")  # -> scrapeable text
dash = export_project(p.trace, fmt="grafana")      # -> importable dashboard JSON
```

Spans are OTel-semantic (`traceId/spanId/attributes`), so swapping to the official
`opentelemetry-sdk` exporter is a one-liner.

## 2. Agent Cryptographic Identity / 加密身份 — `charter/identity.py`

Every agent gets a signed identity; every tool call is HMAC-signed with a nonce +
expiry, then verified. Closes Red Hat's #1 gap (cryptographic identity + tool
governance).

```python
from charter import issue_agent, sign_tool_call, verify_tool_call

issue_agent("dev-1", ["execute_in_sandbox"])
call = sign_tool_call("dev-1", "execute_in_sandbox", {"cmd": "pytest"})
assert verify_tool_call(call, {"cmd": "pytest"})["ok"]
# replay / tamper / capability / expiry all rejected:
assert not verify_tool_call(call, {"cmd": "pytest"})["ok"]   # replayed nonce
assert not verify_tool_call(call, {"cmd": "other"})["ok"]    # digest mismatch
```

Stdlib-only (HMAC-SHA256). Production hardening (v2.1): X.509 agent certs + mTLS.

## 3. Vector Memory / 向量记忆 — `charter/vector_memory.py`

Semantic recall replaces the v1.1 keyword LIKE queries. Default is a
deterministic hashing-trick embedder (stdlib, offline, CI-safe); plug in any
`(text, dim) -> [float]` for a real embedding model.

```python
from charter import VectorMemory
vm = VectorMemory(path="mem.sqlite", dim=128)
vm.remember("dev-1", "we chose SQLite as the cache layer")
vm.recall("dev-1", "cache storage decision", limit=3)  # cosine + recency + salience
```

## 4. SOP Template Marketplace / 行业模板市场 — `charter/templates/`

Pre-governed 10-stage SOPs per domain. Drop a JSON into `charter/templates/`
to ship your own; `list_templates()` discovers it.

```python
from charter import list_templates, apply_template
print([t["name"] for t in list_templates()])
cfg = apply_template({}, "finance")   # strict TDD, 60k budget, SOC2-aligned gates
```

Builtin: `finance` (SOC2), `healthcare` (HIPAA/PHI), `e-commerce` (high-throughput),
`research` (reproducible, TDD off).
