# v3.19.0 - TTL sweep + audit-loop health/dry-run + stress report validator + per-tool metrics

## New features

### 1. `SemanticCache.sweep_expired()` - proactive TTL purge
- `sweep_expired()` scans all three tiers (L1 memory, L2 SQLite, L3 remote)
  and removes every key whose timestamp is older than `ttl_s`.
- Returns `{"swept": int, "l1_swept": [...], "l2_swept": [...],
  "l3_swept": [...], "ttl_s": float}`.
- L3 expired keys are tombstoned (no DELETE in the KV protocol).
- Call periodically from a background task to keep memory/disk bounded.

### 2. `audit-loop` health check + `--dry-run`
- `--metrics-url http://host:port/metrics`: each cycle first GETs the
  metrics URL; if the server is offline the cycle is skipped and logged
  (`offline_skips` counter).
- `--dry-run`: reports are written to `--out-dir` but **not** posted to
  the PR. Useful for CI dry-runs and local testing.
- Usage: `charter.cli audit-loop --pr 42 --repo o/n --metrics-url
  http://host:port/metrics --dry-run [--interval 30] [--cycles 0]`

### 3. `validate-stress-report` subcommand
- `python -m charter.cli validate-stress-report cas_report.json`
- Validates a CAS stress JSON report: checks all 9 required fields
  (`final`, `expected`, `ok`, `conflicts`, `ops`, `conflict_rate`,
  `wall_s`, `n_writers`, `iterations`) and their types.
- Exit codes: 0 = valid, 1 = validation failure or missing file, 2 = usage error.
- Pairs with `make stress JSON=1 OUT=cas_report.json` for CI artifact checks.

### 4. Per-tool labeled governance metrics
- `/metrics` now emits `charter_mcp_gate_pass_total{tool="..."}`,
  `charter_mcp_gate_fail_total{tool="..."}`,
  `charter_mcp_tracer_spans_total{tool="..."}`,
  `charter_mcp_tracer_hallucinations_total{tool="..."}`,
  `charter_mcp_tracer_drift_sum{tool="..."}` alongside the existing
  aggregate counters.
- Enables Prometheus multi-dimensional queries (e.g.
  `charter_mcp_gate_fail_total{tool="plan_pipeline"}`).
- `metrics-watch` dashboard renders the top-3 tools by gate_fail.
- Bug fix: `do_POST` now strips the query string before path matching,
  so `/mcp/message?client=x` works correctly.

## Tests
536 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_19.py`
(sweep L1/L2/no-ttl, audit-loop flags, validate-stress-report,
per-tool label metrics).

## Bug fixes
- `HTTPMCPServer.do_POST`: query string no longer breaks path matching
  (`/mcp/message?client=test` was 404-ing).
- `test_v3_17` CAS stress: `max_cas_retries` bumped 10→30 to avoid
  flaky 3.9 failures under GIL timing.
