# v3.18.0 - Reconcile auto-repair + dual-source dashboard + audit-loop + stress JSON

## New features

### 1. `reconcile(repair=True)` - L1/L2/L3 drift auto-fix
- `SemanticCache.reconcile(repair=True)` auto-fixes cache drift:
  - `in_storage_only` keys (L2/L3 but not L1): back-filled into L1 from
    the freshest tier (L3 first, then L2). If the value is TTL-expired,
    it is purged from all tiers (`_purge_key`).
  - `in_memory_only` keys (L1 but not L2/L3): persisted to L2 and L3.
- Returns `repaired` (list of `{key, action, source}`) and `repairs` (count).
- `_purge_key(key)` removes a key from L1 + L2 + L3 (best-effort tombstone
  on L3 since DELETE is not in the KV protocol).

### 2. `metrics-watch` dual-source (SSE real-time + polling)
- `python -m charter.cli metrics-watch --url .../metrics --sse .../mcp/sse?stream=metrics`
- A background thread consumes the SSE `charter://metrics` event stream and
  renders updates in real time; the main loop polls `/metrics` as a
  fallback / secondary source. SSE events take priority (fresher data).
- No extra dependencies — stdlib `threading` + `urllib`.

### 3. `audit-loop` - periodic governance audit + PR attach
- `python -m charter.cli audit-loop --pr 42 [--repo o/n] [--interval 30] [--cycles 0]`
- Each cycle: runs `demo --gov --trace-out` (writes a fresh JSON audit
  report) → posts it to the GitHub PR via `attach_audit_to_pr`.
- `--cycles 0` = run until Ctrl-C; `--out-dir` controls where reports
  are written.

### 4. `make stress JSON=1` / `make stress OUT=cas_report.json`
- `make stress N=4 I=25 JSON=1` prints the stress result as indented JSON
  (machine-readable, ready for CI artifact archival).
- `make stress N=4 I=25 OUT=cas_report.json` also writes the JSON to a
  file for later analysis.

## Tests
526 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_18.py`
(reconcile backfill/persist/TTL-purge, metrics-watch usage, audit-loop
usage, stress version field).
