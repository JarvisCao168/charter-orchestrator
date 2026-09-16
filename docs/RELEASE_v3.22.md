# v3.22.0 - Auto-register sweeper + webhook SQLite persistence + TIER=custom + dashboard tier table

## New features

### 1. `start_sweeper(http_server=...)` auto-registration
- Pass an `HTTPMCPServer` instance to `SemanticCache.start_sweeper()` and the
  returned handle is automatically registered via `http_server.register_sweeper(handle)`.
- `/metrics` now emits `charter_sweeper_sweeps_total`, `charter_sweeper_keys_swept_total`,
  `charter_sweeper_uptime_seconds`, `charter_sweeper_running` without manual wiring.

### 2. Webhook retry SQLite persistence
- `_webhook_set_db_path(path)` enables crash-safe persistence: the in-memory
  retry queue is mirrored to a SQLite table after every enqueue/dequeue.
- `_webhook_restore_from_db()` loads pending items on startup (deduped by
  `(url, attempt)`), then clears the DB table.
- Without a DB path, behaviour is unchanged (pure in-memory mode).

### 3. `make stress TIER=custom N=8 I=50`
- `TIER=custom` uses the user-supplied `N`/`I` values (default `N=4 I=25`).
- The JSON output now includes a `tier` field: `"tier": "custom"` (or
  `"high"` / `"low"` / `"default"`), plus `n_writers` and `iterations`
  for full reproducibility.

### 4. Dashboard tier-grouped rendering
- `metrics-watch` parses the `tier_breakdown` SSE data line
  (`data: tier_breakdown={"high": {"gate_pass:route_task": 3, ...}}`).
- Every 5th poll render prints a per-tier table:
  ```
  tier-group summary:
       high  gate_pass=3  gate_fail=1
        low  gate_pass=5  gate_fail=0
  ```
- The tier table is also printed on Ctrl-C exit for a final snapshot.

## Tests
559 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_22.py`
(auto-register, SQLite roundtrip, no-DB no-op, custom tier fields,
dual-label parse, tier_breakdown JSON roundtrip).
