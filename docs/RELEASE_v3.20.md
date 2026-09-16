# v3.20.0 - Sweeper thread + webhook audit + CI stress validation + tool+tier metrics

## New features

### 1. `SemanticCache.start_sweeper()` - background GC thread
- `handle = cache.start_sweeper(interval_s=30.0, reconcile=False)`
- Starts a daemon thread that periodically calls `sweep_expired()` (and
  optionally `reconcile(repair=True)`) every `interval_s` seconds.
- The handle exposes `stop()`, `last_sweep`, `last_reconcile`, `running`.
- Thread-safe; `stop()` joins with a 5s timeout.

### 2. `audit-loop --report-to-webhook`
- `--webhook-url https://hooks.slack.com/...` posts a summary after each
  cycle (Slack/Discord/Feishu JSON formats).
- `--webhook-template '{...json...}'` customises the payload template.
- Standard library only; failures are logged, never crash the loop.

### 3. `validate-stress-report --ci`
- `python -m charter.cli validate-stress-report cas_report.json --ci`
- Outputs machine-readable JSON: `{"valid": bool, "errors": [...],
  "file": str, "fields_checked": int}`.
- Exit codes: 0 = valid, 1 = invalid, 2 = usage error.
- Designed for GitHub Actions steps that need to parse the result.

### 4. `/metrics` tool+tier dual-label
- `charter_mcp_gate_pass_total{tool="route_task",tier="high"}` etc.
- Extracts the routing tier from `route_task`/`plan_pipeline` results.
- Enables Prometheus queries like:
  `sum(charter_mcp_gate_fail_total{tier="high"}) by (tool)`

## Tests
546 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_20.py`
(sweeper start/stop/reconcile/no-ttl, webhook flags, --ci valid/invalid/usage,
tool+tier labels, dual-label parse).
