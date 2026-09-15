# v2.7.0 — Multi-System Linkages (Phase 4)

Charter Orchestrator v2.7.0 adds six more production linkages: a K8s
distributed judge pool, LLM auto-naming for memory clusters, Mimir →
Grafana OnCall alert routing, a real k8s SPIRE node-agent socket
handshake model, LLM PR comment auto-completion/rewrite, and S3
versioning / cross-region replication + team RBAC for shared checkpoints.

## New modules

### 1. Distributed judge pool (K8s Job multi-replica) — `charter/judge_pool.py`
- `plan_judge_pool(artifacts, backends, replicas_per_provider)` — builds
  N per-provider K8s Job replicas + a collector Job.
- `render_pool_manifests(plan)` — the ConfigMap + N Judge Jobs + collector
  as JSON docs, ready for `kubectl apply` (offline-safe plan-only without a
  cluster).
- `DistributedJudgePool.aggregate(votes)` — groups replica votes *per
  provider* (averaging them) before the weighted aggregation, so a
  provider with 3 replicas does NOT triple its weight; `details` reports
  `replicas_per_provider`.
- `submit(plan, k8s_client=None)` — creates the Jobs when a kubernetes
  client is bound; plan-only otherwise.

### 2. Memory LLM auto-naming — `charter/cluster_naming.py`
- `name_clusters(clusters, backend)` — attach a 1-3 word `name` +
  one-line `description` to each cluster (from
  `charter.memory_clustering.cluster_episodes`). Pluggable: `LLMClusterNamer`
  when a key is set, `HeuristicClusterNamer` otherwise (top content
  words). Per-cluster LLM failure degrades that cluster to the heuristic
  name (flagged `naming="heuristic-fallback"`).
- `named_cluster_report(store, session_id, agent_id)` — cluster + name a
  session's episodes, store the *named* summaries back as
  `kind="named_cluster"`.

### 3. Mimir → Grafana OnCall alert routing — `charter/oncall_routing.py`
- `oncall_integrations(teams)` — Grafana OnCall integration configs per
  team (Slack / PagerDuty / webhook).
- `oncall_route_policy(rules_by_tenant, integrations, routing_map)` — an
  Alertmanager/OnCall `route` tree mapping
  `{tenant, severity, alertname}` → a team's receiver, with tighter
  escalation for `severity=critical`.
- `route_for_alert(alert, ...)` — which receiver/team a fired alert
  routes to.
- `oncall_provisioning_bundle(...)` — one-shot: integrations + route +
  inhibit + silences as JSON.

### 4. Real k8s SPIRE node-agent socket handshake — `charter/spire_node_handshake.py`
- `WorkloadSocketConfig` — the socket path + trust bundle + agent env a
  pod's main container reads.
- `render_workload_socket_manifests(cfg)` — the k8s pod-spec fragment that
  wires the node agent's socket into the pod (emptyDir + env + a postStart
  hook that pings the socket).
- `validate_workload_socket(cfg)` — offline checks: socket/bundle under the
  node-agent mount, DNS-safe trust domain, service account set.
- `handshake_plan(cfg)` — the ordered connect → attest → fetch_svid →
  verify → mTLS step sequence a reviewer / automation can verify.

### 5. PR comment LLM auto-completion / rewrite — `charter/pr_autosuggest.py`
- `pr_autosuggest(text, ...)` — for one comment: concrete `rewrites`
  (vague → specific), `followups` (questions the reviewer should ask), and
  `action_items` (to-dos). Pluggable: `LLMSuggester` when a key is set,
  `HeuristicSuggester` otherwise.
- `autosuggest_pr_comments(comments)` — batch over a PR's comments + a
  `{rewrites, followups, action_items}` count digest.

### 6. S3 versioning + cross-region replication + team RBAC — `charter/checkpoint_rbac.py`
- `TeamRBAC` — owner / admin / member / viewer role model; `check(role,
  op)` + `enforce(actor_role, op, fn)` gate publish / pull / import /
  audit (a denied op never calls `fn`).
- `s3_versioning_config(bucket)` — bucket-versioning JSON (Enabled +
  MFA) so checkpoint objects are retained on delete / overwrite.
- `s3_cross_region_replication(...)` — an S3 CRR rule mirroring a team's
  checkpoints to a second region (with a team-label filter) + the
  destination bucket's versioning.
- `team_policies(team_roles, ...)` — one-shot: the RBAC table + versioning
  + CRR docs as JSON.

## Tests
+27 new tests in `tests/test_v2_7.py` (140 → 167 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the plan-only / local-fallback /
heuristic / RBAC-deny contracts (judge-pool plan + per-provider
aggregation, cluster naming, OnCall route tree, k8s socket validation +
handshake plan, heuristic autosuggest, RBAC gate + S3 versioning/CRR JSON).

## Install
```
pip install charter-orchestrator            # stdlib-only core
pip install "charter-orchestrator[crypto]"  # + X.509/mTLS/SPIFFE identity
pip install "charter-orchestrator[llm]"     # + HTTP embedders / online judge
pip install "charter-orchestrator[s3]"      # + boto3 for shared checkpoint storage
```

## Roadmap (v2.8)
- Distributed judge pool on a live K8s cluster + results to S3 + autoscaling
- Multi-language memory auto-naming (cross-lingual episode merging)
- OnCall → Grafana OnCall gRPC API (real webhook delivery)
- Real k8s SPIRE node-agent SPIFFE socket bidirectional mTLS test
- LLM diff-level code completion / rewrite suggestions for PR comments
- Team RBAC → real IAM / S3 bucket-policy generation
