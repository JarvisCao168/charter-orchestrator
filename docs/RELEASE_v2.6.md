# v2.6.0 — Multi-System Linkages (Phase 3)

Charter Orchestrator v2.6.0 adds six more production linkages: concurrent
judge voting with result caching, semantic memory clustering, Mimir
multi-tenant provisioning, real k8s SPIRE Agent mTLS artifacts, LLM PR
comment sentiment/specificity, and team-shared checkpoint storage with an
audit log.

## New modules

### 1. Concurrent judge voting + result cache — `charter/judge_concurrency.py`
- `vote_judges_concurrent(...)` runs N provider judges on a
  `concurrent.futures` thread pool; the weighted-voting aggregation is
  identical to `vote_judges` (sequential), so a 4-provider vote takes
  ~max(latency) not sum(latency).
- `JudgeResultCache` (LRU + optional SQLite) keyed by
  (artifact-fingerprint, backend-set, models, weights, threshold).
- `cached_vote(...)` — transparent cache layer; `details["cache_hit"]` is
  True on a hit. Repeated votes for the same artifacts + config are O(1)
  instead of N LLM calls.
- Offline-safe: no live backends → heuristic fallback, and the fallback
  result is cached too.

### 2. Memory vector clustering — `charter/memory_clustering.py`
- `MemoryClusterer` — threshold-based agglomerative clustering over
  embedded episodes (pluggable embedder, default offline hashing). Two
  episodes merge when centroid cosine similarity > `similarity`; stops at
  `max_clusters`.
- `cluster_episodes(...)` — one-shot; returns `[{label, centroid,
  member_ids, top_content, size}]`.
- `cluster_session(store, session_id, agent_id)` — embed + cluster a
  session's raw episodes, store each cluster as a `kind="cluster_summary"`
  memory with high salience so future recall is O(clusters) not
  O(episodes). Reports `reduction` (N → K).
- `cluster_count(...)` — report how much a corpus shrinks.

### 3. Mimir multi-tenant + label propagation — `charter/mimir_multitenant.py`
- `mimir_tenants(projects)` — map each project to a stable Mimir tenant
  user (`charter-<project>`).
- `tenant_rules(project, tenant, ...)` — a Prometheus `groups:` doc scoped
  to one tenant, with tenant + project labels propagated into every rule's
  expr + labels + annotations.
- `label_propagation_config(tenant, ...)` — the Mimir distributor
  `per_tenant_override` shape that adds fixed labels to ingested series.
- `mimir_provisioning_bundle(projects, ...)` — one-shot: tenants +
  per-tenant rules + label propagation + Grafana Mimir/Loki/Tempo data
  sources, all as JSON-ready docs.

### 4. Real k8s SPIRE Agent mTLS — `charter/spire_k8s_mtls.py`
- `K8SSPIREAgentConfig` — the SPIRE Agent's k8s attestation config
  (SA, namespace, workload JWT path, SVID socket, trust bundle, data seeds).
- `render_spire_agent_config(cfg)` — the JSON a real `spire-agent` reads
  (`agent.data_seeds`, `agent.k8s`), ready to write to
  `/run/spire/config/agent.json`.
- `render_agent_values(cfg)` — k8s *values* that mount the SVID socket +
  trust bundle + projected SA token into the pod.
- `mtls_env(cfg)` — the `SPIFFE_ENDPOINT_SOCKET` / `SPIFFE_TLS_*` env vars
  a SPIFFE-enabled app reads to enable mTLS.
- Pure JSON / k8s-values output; the live mTLS handshake happens in the
  pod's sidecar, so CI stays green.

### 5. PR comment LLM sentiment / specificity — `charter/pr_sentiment.py`
- `LLMCommentAnalyzer` / `HeuristicCommentAnalyzer` — pluggable analyzers
  over a comment's *text*: sentiment (−1..1), specificity (0..1),
  actionability, one-line summary.
- `analyze_comment(text, ...)` — one comment.
- `analyze_pr_comments(pr_number, repo, token)` — pulls the PR's review +
  issue comments (offline-safe: no token → empty aggregate, `live=False`)
  and returns per-comment + aggregate
  `{avg_sentiment, avg_specificity, n_actionable, themes}`.
- The aggregate feeds `pr_comment_scoring.score_from_pr` for a richer,
  semantic community score.

### 6. Team shared checkpoint storage (S3/GCS) + audit log — `charter/checkpoint_shared.py`
- `SharedCheckpointStore` — publishes / pulls checkpoints to a shared
  backend: `filesystem` (default), `s3` (boto3 when installed), `gcs`
  (cloud SDK when installed). Missing SDKs degrade to the local directory
  so CI / airgapped use keeps working.
- `AuditLog` — append-only JSONL trail of every publish / pull / import
  (who + when + what + source + ok).
- `publish_to_team` / `pull_from_team` / `audit_report` — the one-shot
  wrappers.

## Tests
+22 new tests in `tests/test_v2_6.py` (118 → 140 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the offline-safe contracts
(concurrent-voting aggregation, cache hit/miss, clustering reduction, Mimir
YAML shapes, k8s SPIRE config JSON, heuristic sentiment, local shared-store
publish/pull + audit).

## Install
```
pip install charter-orchestrator            # stdlib-only core
pip install "charter-orchestrator[crypto]"  # + X.509/mTLS/SPIFFE identity
pip install "charter-orchestrator[llm]"     # + HTTP embedders / online judge
pip install "charter-orchestrator[s3]"      # + boto3 for shared checkpoint storage
```

## Roadmap (v2.7)
- Distributed judge pool (K8s Job multi-replica) for concurrent voting
- LLM cluster labeling + auto-naming for memory clusters
- Mimir → Grafana OnCall alert routing
- Real k8s SPIRE node-agent SPIFFE socket handshake
- LLM auto-completion / rewrite suggestions for PR comments
- S3 versioning + cross-region replication + team RBAC for shared checkpoints
