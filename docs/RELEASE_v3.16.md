# v3.16.0 - CAS stress in CI + audit replay export + shared pipeline L3 + governance metrics

## New features

### 1. Multi-writer CAS stress in CI
- `make stress` (N=4 I=25 default): runs `stress_multi_writer` against a
  reference KV gateway and asserts **no lost updates** (final == expected).
- `make stress-ci`: prints a ready-to-paste, **non-blocking** GitHub Actions
  step (`continue-on-error: true`) so the stress check runs on every CI push
  without gating the build.
- `test_cas_stress_no_lost_updates` guards it in the pytest suite.

### 2. SemanticTrace audit replay
- `SemanticTracer.to_json()` / `export(path)` and module-level
  `export_audit_report(tracer, path)`: a self-contained JSON audit timeline
  (summary + every span: id, ts, tool, similarity, verdict, texts).
- `charter.cli demo --gov --trace-out file.json` writes the report
  end-to-end.

### 3. plan_pipeline shared L3 (cross-process)
- `demo --gov --live-pipeline`: a reference KV gateway hosts the pipeline
  `SemanticCache` L3; two separate python subprocesses run the same
  `plan_pipeline` plan - node-b serves `cached: True` from node-a's write,
  with full routing decisions on both sides.
- Cache key now excludes per-call audit `outputs` so repeated invocations
  hit deterministically.

### 4. Governance audit metrics on /metrics
- `attach_full_governance` + HTTP owner: every `tools/call` now publishes
  `charter_mcp_gate_pass_total`, `charter_mcp_gate_fail_total`,
  `charter_mcp_tracer_spans_total`, `charter_mcp_tracer_hallucinations_total`,
  `charter_mcp_tracer_drift_sum` (Prometheus text format on `/metrics`).

## Tests
514 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_16.py`
(audit export, shared pipeline L3, governance metrics, CAS stress).
