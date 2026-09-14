# v2.4.0 — Multi-System Linkages

Charter Orchestrator v2.4.0 connects the framework to *real* production
systems end-to-end: a multi-model judge, compressed cross-session memory,
SLO → alerting, a live SPIRE Server gateway, and template-marketplace
auto-CI + community scoring.

## New modules

### 1. Multi-model judge consensus — `charter/judge_consensus.py`
`consensus_judge(project_id, artifacts, backends=[...], models=[...])`:
- runs N judge backends (default Agnes + OpenAI) over the same artifacts,
- aggregates mean per-dimension scores + majority verdict,
- computes an **agreement matrix** (per-dimension 1 - normalized std) and an
  overall **confidence**,
- per-judge scores are kept in `details["per_judge"]`; excluded judges are
  flagged.
- **Offline-safe**: when no live backend is available the result degrades to
  the heuristic judge with `details["mode"]="offline-fallback"`.

### 2. Cross-session memory compression — `charter/memory_compress.py`
`compress_session(store, session_id, agent_id, online=True)`:
- pulls a session's raw episodes from a `SessionStore`,
- summarizes them into key facts + a one-line summary (LLM via
  `LLMSummarizer` when a key is set, `HeuristicSummarizer` otherwise),
- writes the summary facts back with `kind="summary"` + higher salience so
  **future sessions recall the distilled knowledge**, not the raw
  episodes.
- `pick_summarizer(backend=...)` auto-detects; failures degrade to the
  heuristic summarizer (flagged in the result).

### 3. Trace SLO → real alerting — `charter/slo_alerts.py`
- `build_alert_payload(slo_summary)` → a normalized `AlertPayload`.
- `fire_alertmanager(payload)` → POST `:9093/api/v2/alerts`.
- `fire_pagerduty(payload)` → POST the Events API v2.
- `SLOAlertGate.evaluate(spans)` → SLO digest + a `should_fire` decision.
- `fire(payload, backend="alertmanager"|"pagerduty"|"none")` — retry-safe:
  an unreachable endpoint returns a report carrying the prepared payload
  instead of raising.

### 4. SPIFFE → real SPIRE Server — `charter/spiffe_grpc.py`
- `connect_spire(target, trust_domain)` opens a gRPC channel to a real SPIRE
  Server and binds the `svid` service stub when the SDK is installed.
- `SPIREGateway.fetch_x509_svid(spiffe_id)` uses the live path when bound,
  and **falls back to the local `TrustDomain` issuer** otherwise, so the
  call shape is identical everywhere (CI-safe).
- `verify_remote_svid(remote, trust_domain)` validates a fetched SVID
  (URI SAN + trust domain + expiry) via `charter.spiffe.verify_svid`.

### 5. Template PR auto-CI + community scoring — `charter/pr_community.py`
- `run_template_ci(spec)` runs the host repo's spec-integrity gate
  (schema / regex / stage ids / budget / JSON-serializable / loader shape)
  against a candidate template and returns a per-check report + a PR body.
- `add_feedback(name, kind)` + `community_score(name)` + `rank_templates()`
  aggregate user **helpful / adopted / reported** signals into a weighted
  per-template score (usefulness 0.5 + adoption 0.3 + health 0.2).
- `template_pr_with_ci(spec, repo, token)` opens the PR (via `github_pr`)
  **and** attaches the CI report + community score to the PR body.

## Tests
+20 new tests in `tests/test_v2_4.py` (74 → 94 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the offline-safe contracts
(consensus fallback, heuristic compression, retry-safe alert payload, local
SPIRE fallback, CI gate + scoring) rather than live network / gRPC calls.

## Install
```
pip install charter-orchestrator            # stdlib-only core
pip install "charter-orchestrator[crypto]"  # + X.509/mTLS/SPIFFE identity
pip install "charter-orchestrator[llm]"     # + HTTP embedders / online judge
pip install "charter-orchestrator[spire]"   # + SPIRE gRPC gateway (grpcio)
```

## Roadmap (v2.5)
- Multi-provider judge voting weighted by historical accuracy
- Hierarchical memory compression (episode → session → project)
- Auto-generated Prometheus Alertmanager rules + real webhooks
- SPIRE gRPC workload attestation
- Real GitHub PR comment/reaction scoring + auto-merge gates
