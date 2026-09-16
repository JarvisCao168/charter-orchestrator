# v3.21.0 - Sweeper stats + webhook retry queue + stress tier + SSE tier breakdown

## New features

### 1. `SweeperHandle.stats()` + `charter_sweeper_*` metrics
- `handle.stats()` returns `{sweeps_total, keys_swept_total, uptime_s,
  running, last_sweep, last_reconcile}`.
- `HTTPMCPServer.register_sweeper(handle)` attaches a handle so `/metrics`
  emits:
  - `charter_sweeper_sweeps_total` (counter)
  - `charter_sweeper_keys_swept_total` (counter)
  - `charter_sweeper_uptime_seconds` (gauge)
  - `charter_sweeper_running` (gauge: 1/0)

### 2. Webhook retry queue with exponential backoff
- Failed webhook POSTs are enqueued in an in-memory retry queue
  (`_WEBHOOK_RETRY_QUEUE`).
- Each subsequent `audit-loop` cycle drains the queue (with backoff:
  2s → 4s → 8s, max 3 attempts).
- `_webhook_enqueue_retry(payload, url, attempt, delay_s)` and
  `_webhook_process_retries()` are exported for testing.

### 3. `make stress TIER=high|low`
- `TIER=high`: 16 writers × 100 rounds × 50 CAS retries (big preset).
- `TIER=low`: 2 writers × 10 rounds × 30 CAS retries (quick smoke).
- `TIER` unset: uses `N`/`I`/`max_cas_retries=30` (default).
- JSON output now includes a `tier` field (`"tier": "high"` / `"low"` /
  `"default"`).

### 4. SSE `tier_breakdown` push
- `/mcp/sse?stream=metrics` event payloads now include a
  `tier_breakdown` dict: `{tier: {gate_pass:<tool>: cnt, ...}}`.
- The dashboard (`metrics-watch`) can render per-tier grouped counters.
- `_broadcast_metrics_change` computes the breakdown under `_gov_lock`
  and forwards it to all subscribed clients.

## Tests
553 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_21.py`
(sweeper stats ×2, webhook retry queue ×2, stress tier field, tier
breakdown payload, webhook post failure).
