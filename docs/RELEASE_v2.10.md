# v3.0.0 — Multi-System Linkages (Phase 7)

Charter Orchestrator v3.0.0 wires the v2.2–v2.9 "real system" candidates
to live infrastructure: a K8s judge-pool deployment bundle, vector-space
cross-language memory merging, real OnCall gRPC end-to-end delivery, a
mock-socket SPIRE bidirectional-mTLS handshake, tree-sitter PR diff
semantics, and an IAM drift-remediation controller. All six degrade to
plan-only / mock / dry-run when the live dependency (a K8s cluster, a
grpc channel, a SPIRE socket, tree-sitter, or a boto3 session) is absent,
so the suite stays green offline.

## New modules

### 1. Judge pool on a real K8s cluster + S3 + KEDA deployment — `charter/judge_pool_deploy.py`
- `JudgePoolDeployment.render_bundle(...)` — a single `kubectl apply -f`
  bundle: the artifacts ConfigMap, the N judge Jobs, the collector Job,
  the cost-aware KEDA ScaledObject, and an S3 result-key ConfigMap the
  collector writes to.
- `kubectl_plan(...)` — the ordered `kubectl` commands to deploy
  (namespace → ConfigMap → Jobs → ScaledObject → collector → S3 key).
- `deploy(k8s_client, ...)` — apply the bundle to a live cluster
  (create each resource); plan-only without a client.
- `verify_deployment(k8s_client, ...)` — post-deploy health probe: the
  ScaledObject exists, the collector Job has `status.succeeded >= 1`, and
  (best-effort) the S3 result key was written.
- `render_judge_pool_bundle(plan, ...)` — the one-shot deployable bundle.

### 2. Cross-language merging in true vector space — `charter/memory_vector_merge.py`
- `merge_in_vector_space(episodes, embed, ...)` — embed each cluster's
  representative with a multilingual-capable embedder (a real LLM
  embedding when a key is set, the offline hashing embedder otherwise),
  then **merge clusters whose centroid vectors are close** — a
  language-agnostic signal that catches same-topic cross-language pairs
  the v2.9 keyword table can't.
- `embed_clusters(...)` / `vector_cross_merge(...)` — the two stages
  (embed each cluster's rep → agglomerative centroid-cosine merge,
  flagging `cross_language=True` when a merge spans ≥2 languages).
- The embedder is pluggable via `charter.embed_cache.production_embedder`;
  the offline path (no LLM key) still runs a real vector space, just
  n-gram-based.

### 3. OnCall real gRPC end-to-end delivery — `charter/oncall_grpc_e2e.py`
- `OnCallGRPCE2E.connect(target)` — open a real `grpc.Channel` (a
  `MockChannel` plan when grpc isn't installed) + bind the OnCall stub.
- `deliver(alert, integration)` — serialize the `OnCallService.Notify`
  request, invoke it, and return a **receipt** (`request_id` +
  delivered status).
- `e2e_delivery_report(...)` — the one-shot verdict a CI / on-call
  pipeline asserts on (channel connected? Notify invoked? receipt status?).

### 4. k8s SPIRE bidirectional-mTLS real node-agent socket handshake — `charter/spire_socket_handshake.py`
- `MockUnixSocket` — an in-memory socket pair that models the
  `SPIFFE_ENDPOINT_SOCKET` Unix-domain socket without a kernel socket
  (runs anywhere, including CI).
- `BidirHandshake.run()` — drives the two-way exchange: the workload
  connects, presents its SVID frame, reads the agent's SVID frame; both
  sides verify the peer (trust-domain match + SPIFFE ID + expiry + URI
  SAN).
- `run_socket_handshake(cfg)` — one-shot report: `connected`, `exchanged`,
  `mtls_established`, the per-side peer-verify results, and the frames.

### 5. PR diff consistency via LSP / tree-sitter — `charter/pr_diff_semantics.py`
- `TreeSitterResolver` — real definition / use analysis (walks
  `function_definition` / `class_definition` / `assignment` nodes for
  definitions, `identifier` / `call` nodes for usages). Imported
  lazily; when tree-sitter isn't installed it degrades to the
  `HeuristicResolver` (the v2.9 identifier-heap).
- `semantic_check(proposals, language, resolver)` — run a semantic
  cross-hunk check: **unpropagated-rename** (a helper renamed in one hunk
  still referenced under the old name elsewhere) and **removed-definition**
  (a symbol deleted in one hunk but still used in another), resolved by
  real definition / usage rather than string matching.
- `semantic_consistency_report(...)` — one-shot: the resolver that ran +
  the inconsistency list + a verdict.

### 6. Checkpoint IAM real AWS apply + auto drift remediation — `charter/checkpoint_iam_remediate.py`
- `IamRemediator.reconcile(team_roles, ...)` — an observe → remediate →
  re-check controller loop: it reads the live drift (missing role /
  stale policy / missing bucket policy), creates the missing role,
  upserts the stale policy, and puts the bucket policy, then re-checks.
- `IamDriftRemediation` — one detected drift + the action that fixed it.
- `reconcile_iam(team_roles, session, dry_run, ...)` — the one-shot
  entry point. Live when a boto3 session is bound; dry-run otherwise
  (the intended actions are recorded + the audit log is still written).

## Tests
+20 new tests in `tests/test_v2_10.py` (213 → 233 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the plan-only / mock / dry-run /
fallback contracts: the K8s bundle + kubectl plan + health probe,
vector-space cross-language merge, the gRPC e2e receipt via a mock
channel, the mock-socket bidir mTLS exchange, semantic symbol resolution
via the resolver fallback, and the IAM reconcile dry-run.

## Install
```
pip install charter-orchestrator            # stdlib-only core
pip install "charter-orchestrator[crypto]"  # + X.509/mTLS/SPIFFE identity
pip install "charter-orchestrator[llm]"     # + HTTP embedders / online judge
pip install "charter-orchestrator[s3]"      # + boto3 for shared checkpoint storage
pip install "charter-orchestrator[k8s]"     # + kubernetes for the live judge pool
pip install "charter-orchestrator[grpc]"    # + grpcio for OnCall gRPC delivery
pip install "charter-orchestrator[tree-sitter]"  # + tree-sitter for diff semantics
```

## Roadmap (v2.11)
- Judge pool end-to-end regression on a real K8s cluster + S3 + KEDA
  scaling observation
- Cross-language merging with a true multilingual embedding model
- OnCall gRPC end-to-end against a live Grafana OnCall instance
- SPIRE bidirectional mTLS against a real node-agent socket (real certs +
  a real handshake)
- PR diff semantics via an LSP server (cross-language, not single-lang
  tree-sitter)
- Checkpoint IAM auto-drift-remediation against a real AWS account
