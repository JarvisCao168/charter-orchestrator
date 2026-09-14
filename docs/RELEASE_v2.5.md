# v2.5.0 — Multi-System Linkages (Phase 2)

Charter Orchestrator v2.5.0 adds six more production linkages: multi-provider
weighted judge voting, three-tier memory compression, auto-generated
Prometheus/Alertmanager rules, SPIRE workload attestation, real GitHub PR
comment scoring, and cross-repo checkpoint sharing.

## New modules

### 1. Multi-provider judge weighted voting — `charter/judge_voting.py`
- `vote_judges(project_id, artifacts, backends, models, weights, ...)`:
  runs N provider judges, aggregates with **weighted voting** (per-provider
  weight, default equal or set via `accuracy_weights` from a labeled gold
  set), weighted mean per-dimension + weighted majority verdict +
  **effective agreement** (1 − weighted normalized std).
- `accuracy_weights(gold, provider_scores)` — rank providers by MAE vs gold;
  more accurate providers vote harder.
- Offline-safe: failed backends are excluded; no votes → heuristic fallback.

### 2. Hierarchical memory compression — `charter/memory_hierarchy.py`
- Three tiers: **episode → session → project**.
- `compress_project(store, project_id, agent_id, session_ids)` rolls session
  summaries into a rolling project digest, stored with `kind="project_summary"`
  + high salience.
- `recall_project(store, agent_id, query)` surfaces the right tier: project
  digest first, then session summaries, then raw episodes.
- Reuses `memory_compress`'s LLM/heuristic summarizers.

### 3. Prometheus/Alertmanager rule auto-gen — `charter/prometheus_rules.py`
- `alert_rules(...)`: emits a `groups:` doc with SLO-aware expressions
  (error ratio, tool-call burst, low uptime) + annotations + runbook links.
- `alertmanager_provisioning(...)`: `route` + `inhibit_rules` +
  `receivers` skeleton.
- `render_provisioning_bundle(...)`: both docs as JSON (a YAML subset),
  ready to drop into Grafana/Prometheus/Alertmanager provisioning.

### 4. SPIRE gRPC workload attestation — `charter/spiffe_attestation.py`
- `build_attestation_request(type, workload_data)` — k8s_pod / workload_jwt /
  opaque, each deriving a well-formed SPIFFE ID.
- `spire_attest(channel, spire_service, trust_domain, attestations)` — POSTs
  to a live SPIRE `svid.Attest` when a channel is bound, else falls back to
  the local `TrustDomain` issuer (same call shape, CI-safe).
- `verify_attestation(result, trust_domain)` — verify the SVID (URI SAN +
  trust domain + expiry) via `charter.spiffe.verify_svid`.

### 5. Real GitHub PR comment scoring — `charter/pr_comment_scoring.py`
- `fetch_pr_signals(pr_number, repo, token)` — GET reviews + comments +
  reactions; returns a `PRSignals` (offline-safe: no token → empty, no raise).
- `score_from_pr(signals)` — fold signals into a 0..1 community score
  (usefulness / adoption / health blend).
- `auto_merge_gate(score, threshold, require_live, min_reviews)` —
  conservative auto-merge decision (requires live signals + min reviews).

### 6. Cross-repo multi-agent checkpoint sharing — `charter/cross_repo.py`
- `CheckpointBus` — file-backed exchange at `~/.charter/checkpoints/`.
- `publish_checkpoint` / `pull_checkpoint` / `list_published` — share
  governance state across repos / processes via JSON files.
- `import_into_core` — pull a published checkpoint and re-inject it into the
  in-process `charter.core` registry.

## Tests
+24 new tests in `tests/test_v2_5.py` (94 → 118 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the offline-safe contracts
(weighted-voting math, hierarchical tiers, rule YAML shapes, attestation
local-fallback, empty PR-signal conservative gate, cross-repo round-trip).

## Install
```
pip install charter-orchestrator            # stdlib-only core
pip install "charter-orchestrator[crypto]"  # + X.509/mTLS/SPIFFE identity
pip install "charter-orchestrator[llm]"     # + HTTP embedders / online judge
```

## Roadmap (v2.6)
- Concurrency + result caching for multi-provider judge voting
- Vector clustering for hierarchical memory (auto-merge same-class episodes)
- Multi-tenant Prometheus (Mimir) + auto label propagation
- Real k8s SPIRE Agent (workload API) mTLS
- LLM sentiment / specificity analysis of PR comments
- Cross-repo checkpoint bus backed by team shared storage (S3/GCS) + audit log
