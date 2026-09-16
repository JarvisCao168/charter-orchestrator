# v3.15.0 - ETag CAS + plan-pipeline caching + full-tool governance audit + true cross-process live demo

## New features

### 1. ETag-style CAS for distributed writes
- `HTTPKeyValueBackend.put_if_version` now uses **412 Precondition Failed**
  semantics (409 still accepted for older gateways).
- New `HTTPKeyValueBackend.cas(key, read, write_fn, max_retries, sleep_s)` -
  observe-then-write CAS loop; `observe(key)` returns `(value, version)` in a
  single GET (no race window between value and version reads).
- New `reference_kv_gateway()` - a thread-hosted reference gateway that
  implements the full versioned surface (`X-If-Version` 412 on mismatch,
  version-continuous envelopes).
- New `stress_multi_writer(n_writers, iterations, base_url)` - N concurrent
  CAS-increment writers; verifies **no lost updates** (final == expected).
- `get_version(key)` on the backend returns the server-side ETag token.

### 2. plan_pipeline decision cache
- `plan_pipeline` MCP tool now caches its full result (critic verdict +
  per-step routing) by a stable BLAKE2b hash of (plan + audit outputs +
  routing params) in a shared `SemanticCache` (L1 memory, optional L2 disk /
  L3 remote via `configure_pipeline_cache`). Re-invoking the same plan
  returns `cached: True` in <1 ms.
- `configure_pipeline_cache(max_entries, disk_path, remote, ttl_s)` exported.

### 3. Full-tool governance audit
- `attach_full_governance(server)` auto-wires ALL 25 MCP tools through
  ValidationGateway + SemanticTracer: per-tool output contracts
  (`_tool_contract`), universal envelope floor, semantic span per call.
- **Bugfix**: the pre-v3.15 `tools/call` tracer recorded a span using
  `text` before it was assigned (latent NameError whenever a tracer was
  attached); now computed first.

### 4. `demo --gov --live` true cross-process
- Spins up a real reference KV gateway, then launches **two separate
  Python subprocesses** (writer / reader). The reader - a fresh process
  with no shared memory - reads the value back through L3, proving
  distributed cache consistency across real process boundaries
  (`hits: 1, version: 1`).

### 5. Version-assert anti-recurrence
- `test_version_is_v3_5` in 3 test files is now **dynamic**: it reads the
  project version from `pyproject.toml` (regex scan, 3.9-safe) instead of a
  hardcoded `startswith("3.x")`, so a future version bump can no longer
  break CI the way it did at v3.12/v3.13/v3.14.

## Tests
509 passed on Python 3.9 / 3.11 / 3.12. New: `tests/test_v3_15.py`
(CAS stress, 412 semantics, plan-pipeline cache, full governance, live subprocess).
