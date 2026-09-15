# v2.8.0 — Multi-System Linkages (Phase 5)

Charter Orchestrator v2.8.0 connects the framework to *real* production
systems at the next level: a live K8s judge pool with S3 persistence and
autoscaling, multilingual memory naming, real Grafana OnCall delivery,
bidirectional k8s SPIRE mTLS, diff-level LLM code completion, and
generated IAM / S3 bucket policies.

## New modules

### 1. Distributed judge pool on a real K8s cluster + S3 + autoscale — `charter/judge_pool_live.py`
- `LiveJudgePool.create(k8s_client)` applies the Job manifests to a live
  cluster (plan-only + manifest return when no client is bound).
- `wait_and_collect(k8s_client)` polls the collector Job's
  `status.succeeded` + the S3 result key; `store_result_to_s3(...)`
  persists the aggregate (retry-safe report when no boto3 client).
- `autoscaler_plan(pool, ...)` emits a KEDA `ScaledObject` (queue-metric
  triggered) + a K8s `HorizontalPodAutoscaler` (CPU fallback).
- `render_live_pool_bundle(...)` — one-shot: Job manifests + KEDA + HPA +
  the S3 result key, all JSON-ready.
- Offline-safe: no k8s client / boto3 → plan-only + payload-only reports.

### 2. Multilingual auto-naming for memory clusters — `charter/cluster_multilingual.py`
- `detect_language(text)` — lightweight, dependency-free detector
  (CJK → zh, kana → ja, hangul → ko, Arabic script → ar, then Latin /
  Cyrillic stopword cues → en/de/es/fr/ru; pure-Latin default → en,
  else "und").
- `multilingual_name_clusters(clusters, ...)` names each cluster **in its
  detected language** (pluggable `LLMMultilingualNamer` /
  `HeuristicMultilingualNamer`), attaching `name` + `description` +
  `language`.
- Per-cluster LLM failure degrades that cluster to the heuristic name.

### 3. Grafana OnCall real delivery — `charter/oncall_deliver.py`
- `OnCallIntegration` + `build_delivery_payload(alert, integration)` —
  the exact OnCall notification body (Slack / PagerDuty / webhook / gRPC
  shapes).
- `OnCallClient.deliver(alert, integration)` — POST to OnCall's
  `/api/v1/integrations/<key>/notification` (or a custom webhook), or a
  structured gRPC `OnCallService.Notify` plan. No base URL / network →
  payload-only report (no exception).
- `route_and_deliver(...)` — resolve the team via
  `oncall_routing.route_for_alert` + deliver in one call.

### 4. Real k8s SPIRE node-agent bidirectional mTLS — `charter/spire_bidir_mtls.py`
- `BidirMTLSConfig` — the two SVIDs (client=workload, server=node agent) +
  trust bundles + socket.
- `build_bidir_mtls_context(cfg)` — the TLS context spec for both
  directions (each side's verify-peer SPIFFE ID = the other's SVID).
- `validate_bidir_mtls(cfg)` — offline checks: both SVIDs under the trust
  domain, trust bundle + socket under the node-agent mount, SA set.
- `render_bidir_k8s_values(cfg)` — k8s values that mount *both* SVID
  secrets + the trust bundle + the env to enable two-way mTLS.
- `attestation_exchange_plan(cfg)` — the ordered two-way steps
  (workload→agent attestation, agent SVID, node attestation, mutual
  verify, mTLS session).

### 5. LLM diff-level code completion for PR comments — `charter/pr_diff_completion.py`
- `complete_diff_hunks(hunks, ...)` — turn a PR's hunks + their review
  comments into concrete `before`/`after` code rewrites + rationale.
  Pluggable: `LLMDiffCompleter` (Agnes/OpenAI) when a key is set,
  `HeuristicDiffCompleter` otherwise (adds targeted `TODO(...)` /
  `CONCERN` lines to the hunk).
- Each `HunkProposal` carries a `as_patch()` unified-diff-shaped snippet
  the reviewer can copy into the PR.

### 6. Checkpoint RBAC → real IAM / S3 bucket policy — `charter/checkpoint_iam.py`
- `iam_policy(team_roles, ...)` — one IAM policy document per role
  (owner / admin / member / viewer), scoped to the team's checkpoint
  bucket + prefix with an auditable principal tag.
- `s3_bucket_policy(team_roles, ...)` — a single S3 *bucket policy*:
  deny-default for destructive / policy actions, then per-role allow
  blocks keyed on the role's IAM ARN + team tag.
- `render_iam_bundle(...)` — one-shot: {role: policy} docs + the bucket
  policy + the role→actions matrix, all JSON-ready for
  `aws iam put-role-policy` / `aws s3api put-bucket-policy`.

## Tests
+25 new tests in `tests/test_v2_8.py` (167 → 192 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the plan-only / payload-only /
heuristic / RBAC-hierarchy contracts (live-pool plan + KEDA/HPA + S3 key,
multilingual detection + naming, OnCall payload + routing, bidir-mTLS
context + validation, diff completion patch shape, IAM / bucket-policy JSON).

## Install
```
pip install charter-orchestrator            # stdlib-only core
pip install "charter-orchestrator[crypto]"  # + X.509/mTLS/SPIFFE identity
pip install "charter-orchestrator[llm]"     # + HTTP embedders / online judge
pip install "charter-orchestrator[s3]"      # + boto3 for shared checkpoint storage
pip install "charter-orchestrator[k8s]"     # + kubernetes for the live judge pool
```

## Roadmap (v2.9)
- Distributed judge pool autoscaling on K8s (multi-trigger KEDA + cost-aware)
- Multilingual memory naming → cross-language episode auto-merging
- OnCall real gRPC channel delivery (non-plan-only)
- k8s SPIRE bidirectional mTLS against a real node-agent socket regression test
- PR diff completion across multiple files + cross-hunk consistency checks
- Checkpoint IAM on real AWS accounts + auto-apply + audit
