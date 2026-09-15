# v2.9.0 — Multi-System Linkages (Phase 6)

Charter Orchestrator v2.9.0 closes the loop on the v2.8 "real system"
candidates: a cost-aware multi-trigger judge pool, cross-language memory
merging, real OnCall gRPC delivery, a k8s SPIRE bidirectional-mTLS
regression test, cross-hunk diff consistency, and real AWS IAM apply +
audit for team checkpoints.

## New modules

### 1. Judge pool multi-trigger + cost-aware autoscaling — `charter/judge_pool_cost.py`
- `JudgePoolAutoscaler` — a KEDA ScaledObject with **multiple triggers**
  (pending-task queue, Prometheus rule breach, calendar window, burst)
  plus a **cost ceiling**: `max_replicas_for_budget(budget, duration_min)`
  computes the largest replica count that fits a $ budget; `scale_decision`
  recommends a replica count that respects the triggers *and* the cost
  cap.
- `render_cost_autoscaler(plan, ...)` — one-shot: the KEDA doc + a
  cost-ceiling block + a scale-decision table across budgets, all JSON.

### 2. Cross-language automatic merging of memory clusters — `charter/memory_cross_language.py`
- `detect_topic_keywords(text, lang)` — CJK technical-term → roman keyword
  table (数据库→database, 连接池→connection+pool, ...) + Latin content
  words, so a zh and an en cluster about the same topic share keywords.
- `cross_language_merge(clusters, keyword_sets, ...)` — merge clusters in
  *different* languages when their keyword Jaccard ≥ threshold or their
  embedding centroids are ≥ 0.85 cosine.
- `merge_cross_language(episodes, ...)` — embed + cluster + merge across
  languages; returns the merged set + a report
  (`N episodes → raw clusters → merged (K cross-language)`).

### 3. Grafana OnCall real gRPC delivery — `charter/oncall_grpc_deliver.py`
- `OnCallGRPCClient.deliver(alert, integration, channel, stub)` — invokes
  the `oncall.OnCallService.Notify` RPC when a gRPC channel + stub are
  bound; otherwise a plan-only report (retry-safe, nothing raises).
- `render_oncall_grpc_stubs(integrations, ...)` — the gRPC service /
  method stubs + a channel config, JSON-ready.

### 4. k8s SPIRE bidirectional-mTLS regression test — `charter/spire_bidir_regression.py`
- `MockNodeAgent` + `MockWorkload` — reference implementations of the
  two-way handshake over the node-agent socket.
- `run_bidir_mtls_regression(cfg)` — checks **6 invariants** (both SVIDs
  under the trust domain, workload verifies agent, agent verifies workload,
  same trust domain, socket under the mount).
- `regression_report(cfg)` — one-shot verdict a CI job can assert on
  (`regression_passed=True` when all hold).

### 5. PR diff cross-file + cross-hunk consistency — `charter/pr_diff_consistency.py`
- `CrossHunkConsistency.detect(proposals)` — catches:
  * **unpropagated-rename** (a helper renamed in one hunk still referenced
    under the old name in another),
  * **removed-definition** (a symbol deleted in one hunk but still used in
    a later one),
  * **conflicting-after** (two proposals for the same hunk with different
    `after` blocks).
- `reconcile_hunks(proposals)` — applies the reconciliation: rename
  propagation, re-introduce removed symbols, keep the longest `after` for
  a same-hunk conflict. Returns `(reconciled, inconsistencies_found)`.
- `cross_file_summary(proposals)` — a per-file digest of the blast radius
  (which files / hunks changed + cross-file symbol dependencies).

### 6. Checkpoint IAM real AWS apply + audit — `charter/checkpoint_iam_apply.py`
- `IamApplier.apply(team_roles, ...)` — when a `boto3` session + account
  are bound: create the per-role IAM roles, attach the policies, and put
  the S3 bucket policy (idempotent; catches EntityAlreadyExists). Without
  a session it returns a **dry-run** report of the exact API calls.
- `IamAuditLog` — append-only JSONL trail of every IAM / S3 mutation
  (who, when, target, account, ok).
- `iam_drift_report(...)` — read the live state and report missing / stale
  roles or policies.
- `apply_iam_policies` / `iam_audit_report` — the one-shot wrappers.

## Tests
+21 new tests in `tests/test_v2_9.py` (192 → 213 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the plan-only / dry-run / mock /
heuristic contracts (cost-capped autoscaler, cross-language merge, gRPC
plan + live mock, bidir-mTLS invariants, cross-hunk reconciliation, IAM
dry-run + audit + a mock-boto3 live apply).

## Install
```
pip install charter-orchestrator            # stdlib-only core
pip install "charter-orchestrator[crypto]"  # + X.509/mTLS/SPIFFE identity
pip install "charter-orchestrator[llm]"     # + HTTP embedders / online judge
pip install "charter-orchestrator[s3]"      # + boto3 for shared checkpoint storage
pip install "charter-orchestrator[k8s]"     # + kubernetes for the live judge pool
```

## Roadmap (v2.10)
- Judge pool on a live K8s cluster + S3 results + a real KEDA deployment
- Cross-language merging in true embedding space (multilingual embeddings)
- OnCall over a live gRPC channel (end-to-end, non-plan-only)
- SPIRE bidirectional mTLS against a real node-agent socket (real certs +
  a real handshake)
- Cross-hunk consistency via LSP / tree-sitter (true semantics, not
  heuristics)
- Checkpoint IAM auto-apply on a real AWS account + audit + auto drift
  remediation
