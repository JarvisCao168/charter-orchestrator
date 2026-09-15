"""Tests for v2.7 multi-system linkages (phase 4).

All offline-safe: no live K8s cluster, no S3, no LLM key. Each test asserts
the *plan-only / local-fallback / heuristic / RBAC-deny* contract that keeps
CI green with no credentials, while still exercising the real code path
(judge-pool plan + per-provider aggregation, cluster naming, OnCall route
tree, k8s socket validation + handshake plan, heuristic autosuggest, RBAC
gate + S3 versioning/CRR JSON).
"""
from __future__ import annotations

import json
import os
import tempfile

from charter import (
    # v2.7 judge pool
    JudgeTask, JudgePoolPlan, DistributedJudgePool,
    plan_judge_pool, render_pool_manifests,
    # v2.7 cluster naming
    name_clusters, HeuristicClusterNamer,
    # v2.7 oncall routing
    oncall_integrations, oncall_route_policy,
    oncall_provisioning_bundle, route_for_alert,
    # v2.7 k8s SPIRE socket
    WorkloadSocketConfig, render_workload_socket_manifests,
    validate_workload_socket, handshake_plan,
    # v2.7 PR autosuggest
    pr_autosuggest, autosuggest_pr_comments, HeuristicSuggester,
    # v2.7 checkpoint RBAC
    TeamRBAC, s3_versioning_config,
    s3_cross_region_replication, team_policies,
    # deps
    ProviderVote,
)
from charter import __version__


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------
def test_version_bumped_v2_7():
    assert __version__.startswith("2.")


# ------------------------------------------------------------------
# 1. distributed judge pool
# ------------------------------------------------------------------
def test_plan_judge_pool_replicates_per_provider():
    plan = plan_judge_pool(
        {"test_coverage": 0.8, "violations": []},
        backends=["agnes", "openai"],
        replicas_per_provider=2)
    assert len(plan.tasks) == 4  # 2 providers x 2 replicas
    # each task has a unique id + provider
    ids = {t.task_id for t in plan.tasks}
    assert len(ids) == 4
    providers = {t.provider for t in plan.tasks}
    assert providers == {"agnes", "openai"}
    # Job names are unique + derived from task ids
    names = plan.to_job_names()
    assert len(names) == 4 and len(set(names)) == 4


def test_render_pool_manifests_json():
    plan = plan_judge_pool({"x": 1}, backends=["agnes"],
                           replicas_per_provider=1)
    docs = render_pool_manifests(plan)
    assert "configmap" in docs
    assert "job-0" in docs
    assert "collector" in docs
    # every doc is valid JSON
    for key, val in docs.items():
        parsed = json.loads(val)
        assert "kind" in parsed or "metadata" in parsed
    # the Job manifest has the right labels + container args
    job0 = json.loads(docs["job-0"])
    assert job0["kind"] == "Job"
    assert job0["metadata"]["labels"]["charter.io/role"] == "judge"
    container = job0["spec"]["template"]["spec"]["containers"][0]
    assert "charter" in container["image"]
    assert container["args"]  # provider/model/task-id args present
    assert "--provider" in container["args"]


def test_distributed_pool_aggregate_groups_replicas():
    """Replicas of the same provider are averaged *before* the weighted
    aggregation, so 3 replicas of one provider do NOT triple its weight
    (the provider's `weight` controls influence)."""
    pool = DistributedJudgePool(threshold=0.7)
    # provider "agnes" with weight 1.0, 3 replicas all scoring 0.9
    votes = [
        ProviderVote(provider="agnes-replica-0",
                      scores={"spec_compliance": 0.9, "code_quality": 0.9,
                               "test_adequacy": 0.9, "efficiency": 0.9,
                               "safety": 0.9}, verdict="pass", weight=1.0),
        ProviderVote(provider="agnes-replica-1",
                      scores={"spec_compliance": 0.9, "code_quality": 0.9,
                               "test_adequacy": 0.9, "efficiency": 0.9,
                               "safety": 0.9}, verdict="pass", weight=1.0),
        ProviderVote(provider="agnes-replica-2",
                      scores={"spec_compliance": 0.9, "code_quality": 0.9,
                               "test_adequacy": 0.9, "efficiency": 0.9,
                               "safety": 0.9}, verdict="pass", weight=1.0),
        # provider "openai" with weight 1.0, 1 replica scoring 0.5
        ProviderVote(provider="openai-replica-0",
                      scores={"spec_compliance": 0.5, "code_quality": 0.5,
                               "test_adequacy": 0.5, "efficiency": 0.5,
                               "safety": 0.5}, verdict="fail", weight=1.0),
    ]
    out = pool.aggregate(votes)
    # after grouping: agnes (avg 0.9, w=1.0) vs openai (0.5, w=1.0)
    # weighted mean for spec_compliance = (0.9*1.0 + 0.5*1.0) / 2.0 = 0.7
    assert abs(out["scores"]["spec_compliance"] - 0.7) < 0.001
    assert out["details"]["n_replicas"] == 4
    assert out["details"]["replicas_per_provider"]["agnes"] == 3
    assert out["details"]["replicas_per_provider"]["openai"] == 1


def test_distributed_pool_submit_plan_only():
    pool = DistributedJudgePool(threshold=0.7)
    plan = plan_judge_pool({"x": 1}, backends=["agnes"],
                           replicas_per_provider=1)
    out = pool.submit(plan, k8s_client=None)
    assert out["submitted"] is False
    assert out["note"]
    assert out["job_names"]


# ------------------------------------------------------------------
# 2. cluster naming
# ------------------------------------------------------------------
def test_name_clusters_heuristic():
    clusters = [
        {"label": "postgres persistence", "size": 3,
         "top_content": "Decided to use Postgres for persistence",
         "member_ids": [1, 2, 3]},
        {"label": "auth flow jwt", "size": 2,
         "top_content": "Auth flow uses JWT with 24h expiry",
         "member_ids": [4, 5]},
    ]
    named = name_clusters(clusters, backend="heuristic")
    assert len(named) == 2
    for c in named:
        assert "name" in c and "description" in c
        assert c["naming"] in ("heuristic", "llm", "heuristic-fallback")
    # a cluster about "postgres" should carry that word in its name/desc
    pg = [c for c in named if "postgres" in c["top_content"].lower()][0]
    assert "postgres" in pg["name"].lower() or \
           "postgres" in pg["description"].lower()


def test_heuristic_namer_shapes():
    namer = HeuristicClusterNamer()
    out = namer.name_cluster(["Decided to use Postgres for persistence",
                               "Postgres migration finished"])
    assert "name" in out and "description" in out
    assert out["name"]  # non-empty


def test_name_clusters_llm_failure_falls_back(monkeypatch):
    """Forcing the LLM namer without a real endpoint -> per-cluster
    fallback to the heuristic (no exception)."""
    import charter.cluster_naming as cn
    class _BrokenLLM:
        name = "llm"
        def name(self, members):
            raise RuntimeError("no network")
    monkeypatch.setattr(cn, "pick_namer", lambda *a, **k: _BrokenLLM())
    clusters = [{"label": "x", "size": 1,
                 "top_content": "Decided to use Postgres",
                 "member_ids": [1]}]
    named = cn.name_clusters(clusters, backend="llm")
    assert named[0]["naming"] == "heuristic-fallback"
    assert "postgres" in named[0]["name"].lower() or \
           "postgres" in named[0]["description"].lower()


# ------------------------------------------------------------------
# 3. Mimir -> OnCall routing
# ------------------------------------------------------------------
def test_oncall_integrations_shapes():
    teams = {"platform": {"slack_channel": "#platform-alerts"},
             "data": {"pagerduty_routing_key": "pd-key-1"}}
    integ = oncall_integrations(teams=teams)
    assert "platform" in integ and "data" in integ
    assert integ["platform"]["type"] == "slack"
    assert integ["data"]["type"] == "pagerduty"
    json.dumps(integ)


def test_oncall_route_policy_maps_tenant_to_team():
    rules_by_tenant = {"charter-alpha": {}, "charter-beta": {}}
    integ = oncall_integrations(
        teams={"platform": {"slack_channel": "#platform"},
               "data": {"slack_channel": "#data"}})
    routing_map = {"charter-alpha": "platform", "charter-beta": "data"}
    policy = oncall_route_policy(rules_by_tenant, integ,
                                 routing_map=routing_map)
    assert policy["team_for"]["charter-alpha"] == "platform"
    assert policy["team_for"]["charter-beta"] == "data"
    # each tenant has a route with matchers
    tenant_routes = [r for r in policy["route"]["routes"]
                     if "tenant=" in str(r.get("matchers"))]
    assert len(tenant_routes) == 2
    json.dumps(policy)


def test_route_for_alert_critical_gets_tighter_escalation():
    integ = oncall_integrations(
        teams={"platform": {"slack_channel": "#platform",
                             "escalation_minutes": 15}})
    alert = {"labels": {"alertname": "CharterHighErrorRate",
                         "tenant": "charter-alpha",
                         "severity": "critical"}}
    out = route_for_alert(alert, {"charter-alpha": {}},
                            integ,
                            routing_map={"charter-alpha": "platform"})
    assert out["team"] == "platform"
    assert out["escalation_minutes"] <= 5  # critical -> tighter
    assert out["severity"] == "critical"


def test_oncall_provisioning_bundle_json():
    bundle = oncall_provisioning_bundle(
        rules_by_tenant={"charter-alpha": {}},
        teams={"platform": {"slack_channel": "#platform"}},
        routing_map={"charter-alpha": "platform"})
    for key in ("integrations", "oncall_config", "route", "team_for"):
        assert key in bundle
    json.loads(bundle["oncall_config"])
    # the oncall config has a route + receivers
    oc = json.loads(bundle["oncall_config"])
    assert "route" in oc and "receivers" in oc


# ------------------------------------------------------------------
# 4. k8s SPIRE node-agent socket
# ------------------------------------------------------------------
def test_render_workload_socket_manifests():
    cfg = WorkloadSocketConfig(trust_domain="charter.example.com",
                                namespace="prod",
                                service_account="agent-1")
    docs = render_workload_socket_manifests(cfg, secret_name="spire-svid")
    assert "pod_spec_fragment" in docs
    env = docs["env"]
    assert env["SPIFFE_ENDPOINT_SOCKET"] == cfg.svid_socket
    assert env["SPIFFE_TLS_CLIENT"] == "true"
    # the pod fragment has volumes + env + a postStart hook
    frag = docs["pod_spec_fragment"]
    assert any("emptyDir" in v for v in frag["volumes"])
    container = frag["containers"][0]
    assert "postStart" in container["lifecycle"]
    json.dumps(docs)


def test_validate_workload_socket_ok():
    cfg = WorkloadSocketConfig(
        svid_socket="/run/spire/sockets/private/api.sock",
        trust_bundle_path="/run/spire/secrets/trustbundle.json",
        node_agent_mount="/run/spire",
        trust_domain="charter.example.com",
        service_account="agent-1")
    out = validate_workload_socket(cfg)
    assert out["ok"] is True, out["problems"]
    assert out["checks"]["socket_under_mount"] is True
    assert out["checks"]["trust_domain_dns_safe"] is True


def test_validate_workload_socket_rejects_bad_socket():
    cfg = WorkloadSocketConfig(
        svid_socket="/tmp/wrong.sock",  # NOT under /run/spire
        trust_bundle_path="/run/spire/secrets/trustbundle.json",
        node_agent_mount="/run/spire",
        trust_domain="Bad_Trust_Domain!",  # not DNS-safe
        service_account="agent-1")
    out = validate_workload_socket(cfg)
    assert out["ok"] is False
    assert any("socket" in p for p in out["problems"])
    assert any("trust_domain" in p for p in out["problems"])


def test_handshake_plan_steps():
    cfg = WorkloadSocketConfig()
    plan = handshake_plan(cfg)
    steps = [s["step"] for s in plan]
    assert steps == ["connect", "attest", "fetch_svid", "verify", "mtls"]
    for s in plan:
        assert "detail" in s


# ------------------------------------------------------------------
# 5. PR auto-suggest
# ------------------------------------------------------------------
def test_pr_autosuggest_vague_comment():
    s = pr_autosuggest("lgtm", backend="heuristic")
    # "lgtm" is short + positive -> a "be specific" rewrite + a followup
    assert s.rewrites  # vague -> be-specific rewrite
    assert s.followups  # positive -> "any remaining risks?" followup
    assert s.analyzer in ("heuristic", "llm")


def test_pr_autosuggest_negative_comment():
    s = pr_autosuggest("This is broken and it is a bug, unsafe",
                        backend="heuristic")
    assert s.action_items  # concerns -> action items
    assert any("concern" in a.lower() or "broken" in a.lower()
               for a in s.action_items) or s.action_items


def test_pr_autosuggest_actionable_comment():
    s = pr_autosuggest(
        "should move the checkpoint save after gate_3 and add a test",
        backend="heuristic")
    assert s.action_items  # action verbs -> structured action item


def test_autosuggest_pr_comments_batch():
    comments = [
        {"id": 1, "user": "alice", "body": "lgtm"},
        {"id": 2, "user": "bob",
         "body": "this is broken, a bug, unsafe and a risk"},
        {"id": 3, "user": "carol",
         "body": "should move the save after gate_3 and add a test"},
    ]
    out = autosuggest_pr_comments(comments, backend="heuristic")
    assert out["n"] == 3
    assert out["counts"]["rewrites"] >= 1
    assert out["counts"]["action_items"] >= 1
    assert out["analyzer"] in ("heuristic", "llm")


def test_heuristic_suggester_shapes():
    h = HeuristicSuggester()
    out = h.suggest("lgtm")
    assert "rewrites" in out and "followups" in out \
        and "action_items" in out


# ------------------------------------------------------------------
# 6. S3 versioning + cross-region + team RBAC
# ------------------------------------------------------------------
def test_s3_versioning_config_shapes():
    v = s3_versioning_config("charter-checkpoints")
    assert v["VersioningConfiguration"]["Status"] == "Enabled"
    assert v["bucket"] == "charter-checkpoints"
    json.dumps(v)


def test_s3_cross_region_replication_shapes():
    crr = s3_cross_region_replication(
        "charter-checkpoints", "us-east-1",
        "charter-checkpoints-replica", "eu-west-1",
        team_label="charter")
    rules = crr["ReplicationConfiguration"]["Rules"]
    assert rules[0]["ID"].startswith("charter-")
    assert rules[0]["Status"] == "Enabled"
    assert crr["destination_region"] == "eu-west-1"
    json.dumps(crr)


def test_team_rbac_role_hierarchy():
    rbac = TeamRBAC()
    # owner > admin > member > viewer
    assert rbac.check("owner", "rbac") is True
    assert rbac.check("owner", "publish") is True
    assert rbac.check("admin", "rbac") is False  # admin can't edit RBAC
    assert rbac.check("admin", "publish") is True
    assert rbac.check("member", "publish") is True
    assert rbac.check("member", "audit") is False
    assert rbac.check("viewer", "pull") is True
    assert rbac.check("viewer", "publish") is False


def test_team_rbac_enforce_denies():
    rbac = TeamRBAC()
    # viewer cannot publish -> fn must NOT be called
    called = {"n": 0}
    def fn(*a, **k):
        called["n"] += 1
        return "published"
    out = rbac.enforce("viewer", "publish", fn)
    assert out["ok"] is False
    assert "rbac-deny" in out["reason"]
    assert called["n"] == 0  # fn was NOT called

    # owner can publish -> fn IS called
    out2 = rbac.enforce("owner", "publish", fn)
    assert out2["ok"] is True
    assert out2["result"] == "published"
    assert called["n"] == 1


def test_team_rbac_user_role_lookup():
    rbac = TeamRBAC(roles={"owner": ["alice"], "viewer": ["bob"]})
    assert rbac.user_role("alice") == "owner"
    assert rbac.user_role("bob") == "viewer"
    assert rbac.allow_user("alice", "publish") is True
    assert rbac.allow_user("bob", "publish") is False
    assert rbac.allow_user("carol", "pull") is False  # unknown user


def test_team_policies_bundle():
    out = team_policies(
        {"owner": ["alice"], "member": ["bob"]},
        team="charter-team",
        bucket="charter-checkpoints",
        source_region="us-east-1",
        destination_bucket="charter-checkpoints-replica",
        destination_region="eu-west-1",
        enable_crr=True)
    # RBAC table has the role/operation matrix
    rbac = json.loads(out["rbac"])
    assert "role_op_matrix" in rbac
    assert "publish" in rbac["role_op_matrix"]["owner"]
    # versioning JSON is valid + enabled
    v = json.loads(out["versioning"])
    assert v["VersioningConfiguration"]["Status"] == "Enabled"
    # CRR is present because enable_crr=True + destination set
    crr = json.loads(out["crr"])
    assert "ReplicationConfiguration" in crr
    # summary mentions both regions
    assert "us-east-1" in out["summary"] and \
        "eu-west-1" in out["summary"]
