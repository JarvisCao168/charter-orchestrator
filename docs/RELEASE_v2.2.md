# v2.2.0 — Production Linkages

Charter Orchestrator v2.2.0 wires the framework to **real production systems**:
an online LLM-as-judge, cross-session persistent memory, and a full
OpenTelemetry → Jaeger/Tempo trace pipeline with SLO reporting.

## New modules

### 1. Online LLM-as-judge — `charter/llm_judge_online.py`
Replaces the offline heuristic judge with a **real LLM judge**:
- `AgnesJudge` / `OpenAIJudge` — provider-agnostic OpenAI-compatible backends
  over stdlib `urllib` (no `requests` hard dep).
- `make_judge(...)` auto-detects a key from `AGNES_API_KEY` / `OPENAI_API_KEY`.
- **Graceful degradation contract**: when no key is configured or the HTTP call
  fails, `score_with_judge(..., online=True)` transparently falls back to the
  deterministic heuristic judge and flags `details["judge"]` — so CI and
  airgapped use stay green with no key.
- Same output shape as `evaluate_agent`, drop-in for callers.

### 2. Cross-session persistent memory — `charter/session_store.py`
Closes the "cross-session recall" gap from the v1.0 peer review:
- File-backed SQLite (`~/.charter/sessions.db`), **WAL mode** → multi-process
  safe.
- `open_session` / `remember` / `recall` / `query`: semantic recall via the
  pluggable `VectorMemory` embedder (default offline hashing, swap for an LLM).
- Rank = `0.5·similarity + 0.3·recency + 0.2·salience`.
- `query()` searches **across sessions** so a new session surfaces what a
  previous one learned.

### 3. Full OTel → Jaeger/Tempo link — `charter/trace_link.py`
Lifts `otel_export` (batch + Prometheus + dashboard) into an end-to-end
pipeline:
- `JaegerPush` / `TempoPush` — retry-safe OTLP/JSON exporters; an unreachable
  backend returns a *pending* payload instead of raising.
- `JaegerQuery.fetch` — read spans back from a Jaeger v2/v1 HTTP backend.
- `aggregate_traces` — per-service SLO digest (span counts, p50/p95 latency,
  error rate, RPS).
- `slo_summary` — boolean SLO-MET / SLO-BREACHED verdict against p95 + error-rate targets.
- `TraceLink` façade ties export + read-back + SLO together.

## Tests
+16 new tests in `tests/test_v2_2.py` (40 → 56 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the **degradation / retry-safe
contracts**, not live network calls, so the suite runs offline.

## Install
```
pip install charter-orchestrator          # stdlib-only core
pip install "charter-orchestrator[crypto]"# + X.509/mTLS identity
pip install "charter-orchestrator[llm]"   # + HTTP embedders / online judge
```

## Roadmap (v2.3)
- Real mTLS (server-side cert verification)
- Template marketplace → GitHub PR automation
- LLM-embedder production endpoint + cache
- PKI-backed identity (CAs / SPIFFE)
