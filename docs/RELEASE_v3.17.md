# v3.17.0 - Governance dashboard + PR audit attach + parameterized CAS + cache reconcile

## New features

### 1. Governance audit dashboard (`metrics-watch`)
- `python -m charter.cli metrics-watch --url http://host:port/metrics [--interval 2.0]`
  - Terminal dashboard polling the MCP `/metrics` endpoint
  - Renders the 5 governance audit counters (gate pass/fail, tracer spans /
    hallucinations / drift) with per-interval deltas. Ctrl-C to stop.
  - Parses Prometheus text exposition (labeled + bare metrics).

### 2. Audit reports into PRs (`attach-audit`)
- `python -m charter.cli attach-audit --report gov_audit.json --pr 123 [--repo o/n]`
  - Posts a `--trace-out` audit report to a GitHub PR as a fenced-JSON comment
  - Prefers the local `gh` CLI; falls back to the REST API with
    `CHARTER_GITHUB_TOKEN` / `GITHUB_TOKEN`.

### 3. Parameterized CAS stress
- `stress_multi_writer` now reports `ops`, `conflict_rate`, `wall_s` in
  addition to `final`/`expected`/`ok` (collision-rate stats).
- `make stress-big`: 16 writers x 100 rounds, 50 CAS retries - a
  high-contention preset for the no-lost-updates guarantee.

### 4. SemanticCache L1/L2/L3 consistency reconcile
- `SemanticCache.reconcile()`: scans L1 (memory), L2 (disk) and L3 (remote)
  and reports which keys exist in which tier; flags `in_memory_only` /
  `in_storage_only` drift and a `consistent` verdict.
- `HTTPKeyValueBackend.list_keys()` (best-effort `GET /kv/_keys`, empty on
  unsupported gateways); the reference gateway now serves `/kv/_keys`.

## Tests
520 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_17.py`
(metrics parsing, CLI subcommand guards, CAS stats, reconcile drift).
