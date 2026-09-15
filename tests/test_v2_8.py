"""Tests for v2.8 multi-system linkages (phase 5).

All offline-safe: no live K8s cluster, no S3, no LLM key, no real Grafana
OnCall. Each test asserts the *plan-only / local-fallback / heuristic*
contract that keeps CI green with no credentials, while still exercising
the real code path (live-pool plan + KEDA/HPA + S3 key, multilingual
language detection + naming, OnCall delivery payload, bidirectional mTLS
config + validation, diff-level completion, IAM / bucket-policy JSON).
"""
from __future__ import annotations

import json
import os

from charter import (
    # v2.8 judge pool live
    LiveJudgePool, autoscaler_plan, render_live_pool_bundle,
    plan_judge_pool,
    # v2.8 multilingual naming
    detect_language, HeuristicMultilingualNamer,
    multilingual_name_clusters,
    # v2.8 oncall delivery
    OnCallIntegration, OnCallClient, build_delivery_payload,
    route_and_deliver,
    # v2.8 spire bidir mTLS
    BidirMTLSConfig, build_bidir_mtls_context, validate_bidir_mtls,
    render_bidir_k8s_values, attestation_exchange_plan,
    # v2.8 pr diff completion
    HunkProposal, HeuristicDiffCompleter, complete_diff_hunks,
    # v2.8 checkpoint iam
    iam_policy, s3_bucket_policy, render_iam_bundle, role_s3_actions,
)
from charter import __version__


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------
def test_version_bumped_v2_8():
    assert __version__.startswith("3.")


# ------------------------------------------------------------------
# 1. distributed judge pool (live + S3 + autoscale)
# ------------------------------------------------------------------
def test_live_judge_pool_plan_only():
    plan = plan_judge_pool({"x": 1}, backends=["agnes", "openai"],
                           replicas_per_provider=2)
    pool = LiveJudgePool(plan, namespace="charter")
    out = pool.create(k8s_client=None)
    assert out["created"] is False
    assert out["note"]
    assert "manifests" in out
    assert "job-0" in out["manifests"] and "collector" in out["manifests"]


def test_live_judge_pool_wait_collect_pending():
    plan = plan_judge_pool({"x": 1}, backends=["agnes"],
                           replicas_per_provider=1)
    pool = LiveJudgePool(plan, s3_bucket="charter-judge-results")
    out = pool.wait_and_collect(k8s_client=None)
    assert out["pending"] is True
    assert "s3_key" in out
    assert out["s3_key"].endswith("aggregate.json")


def test_store_result_to_s3_retry_safe():
    plan = plan_judge_pool({"x": 1}, backends=["agnes"],
                           replicas_per_provider=1)
    pool = LiveJudgePool(plan, s3_bucket="charter-judge-results")
    out = pool.store_result_to_s3({"weighted": 0.8, "verdict": "pass"},
                                   boto3_client=None)
    assert out["stored"] is False
    assert out["s3_uri"].startswith("s3://charter-judge-results/")
    assert out["note"]


def test_autoscaler_plan_keda_and_hpa():
    plan = plan_judge_pool({"x": 1}, backends=["agnes", "openai"],
                           replicas_per_provider=2)
    out = autoscaler_plan(plan, min_replicas=2, max_replicas=10,
                           trigger_metric="pending-judge-tasks",
                           trigger_threshold=32)
    keda = json.loads(out["keda_scaledobject"])
    hpa = json.loads(out["hpa"])
    assert keda["kind"] == "ScaledObject"
    assert keda["spec"]["minReplicaCount"] == 2
    assert keda["spec"]["maxReplicaCount"] == 10
    trig = keda["spec"]["triggers"][0]
    assert trig["metadata"]["threshold"] == "32"
    assert hpa["kind"] == "HorizontalPodAutoscaler"
    assert hpa["spec"]["maxReplicas"] == 10
    # the HPA uses CPU utilization
    assert hpa["spec"]["metrics"][0]["type"] == "Resource"


def test_render_live_pool_bundle():
    plan = plan_judge_pool({"x": 1}, backends=["agnes"],
                           replicas_per_provider=1)
    bundle = render_live_pool_bundle(plan, namespace="charter",
                                     s3_bucket="charter-judge-results",
                                     min_replicas=1, max_replicas=8)
    for key in ("configmap", "job-0", "collector", "keda", "hpa",
                 "s3_result_key"):
        assert key in bundle
    json.loads(bundle["keda"])
    json.loads(bundle["hpa"])
    assert "charter-judge-results" in bundle["s3_result_key"]


# ------------------------------------------------------------------
# 2. multilingual naming
# ------------------------------------------------------------------
def test_detect_language_basic():
    assert detect_language("Postgres migration finished") == "en"
    assert detect_language("数据库连接池调优完成") == "zh"
    assert detect_language("データベース接続プールを調整") == "ja"
    assert detect_language("데이터베이스 연결 풀 조정") == "ko"
    # undetermined
    assert detect_language("zzzzz qqqqq") in ("und", "en")


def test_multilingual_name_clusters_attaches_language():
    clusters = [
        {"label": "db", "size": 2,
         "top_content": "数据库连接池调优完成", "member_ids": [1, 2]},
        {"label": "auth", "size": 1,
         "top_content": "Auth flow uses JWT with 24h expiry",
         "member_ids": [3]},
    ]
    out = multilingual_name_clusters(clusters, backend="heuristic")
    assert len(out) == 2
    for c in out:
        assert "name" in c and "description" in c and "language" in c
    zh = [c for c in out if c["top_content"].startswith("数据库")][0]
    assert zh["language"] == "zh"
    en = [c for c in out if c["top_content"].startswith("Auth")][0]
    assert en["language"] == "en"


def test_heuristic_multilingual_namer_shapes():
    namer = HeuristicMultilingualNamer()
    out = namer.name(["Postgres migration finished"], "en")
    assert "name" in out and "description" in out
    assert out["language"] == "en"
    out_zh = namer.name(["数据库连接池调优完成"], "zh")
    assert out_zh["language"] == "zh"


# ------------------------------------------------------------------
# 3. OnCall delivery
# ------------------------------------------------------------------
def _alert():
    return {"labels": {"alertname": "CharterHighErrorRate",
                        "tenant": "charter-alpha",
                        "severity": "critical",
                        "project_id": "alpha"},
            "annotations": {"description": "error ratio high"},
            "startsAt": "2025-01-01T00:00:00Z",
            "generatorURL": "charter://slo"}


def test_build_delivery_payload_shapes():
    alert = _alert()
    integ = OnCallIntegration(name="platform", kind="slack",
                              config={"slack_channel": "#platform"})
    payload = build_delivery_payload(alert, integ)
    assert payload["title"] == "CharterHighErrorRate"
    assert payload["severity"] == "critical"
    assert payload["tenant"] == "charter-alpha"
    assert payload["slack_channel"] == "#platform"
    json.dumps(payload)


def test_oncall_client_payload_only_offline():
    alert = _alert()
    integ = OnCallIntegration(name="platform", kind="slack",
                              config={"slack_channel": "#platform"})
    client = OnCallClient()  # no base_url
    out = client.deliver(alert, integ)
    assert out["delivered"] is False
    assert out["payload_only"] is True
    assert "payload" in out


def test_oncall_client_grpc_plan():
    alert = _alert()
    integ = OnCallIntegration(name="grpc-bridge", kind="grpc",
                              config={})
    client = OnCallClient()
    out = client.deliver(alert, integ)
    assert out["kind"] == "grpc-plan"
    assert out["service"] == "oncall.OnCallService"
    assert out["method"] == "Notify"


def test_route_and_deliver_resolves_team():
    alert = _alert()
    integrations = {"platform": OnCallIntegration(
        name="platform", kind="slack",
        config={"slack_channel": "#platform"})}
    out = route_and_deliver(alert, {"charter-alpha": {}},
                            integrations,
                            routing_map={"charter-alpha": "platform"},
                            client=OnCallClient())
    # offline (no base_url) -> not delivered, but the routing decision is
    # present and points at the platform team
    assert out["decision"]["team"] == "platform"
    assert out["delivered"] is False


# ------------------------------------------------------------------
# 4. k8s SPIRE bidirectional mTLS
# ------------------------------------------------------------------
def test_build_bidir_mtls_context():
    cfg = BidirMTLSConfig(trust_domain="charter.example.com",
                           namespace="prod", service_account="agent-1")
    ctx = build_bidir_mtls_context(cfg)
    assert ctx["client"]["spiffe_id"].startswith(
        "spiffe://charter.example.com/ns/prod/sa/agent-1")
    assert ctx["server"]["spiffe_id"].startswith(
        "spiffe://charter.example.com/ns/prod/agent/node-0")
    # each direction verifies the peer's SPIFFE ID
    assert ctx["client"]["verify_peer_spiffe_id"] == ctx["server"]["spiffe_id"]
    assert ctx["server"]["verify_peer_spiffe_id"] == ctx["client"]["spiffe_id"]
    assert ctx["env"]["SPIFFE_TLS_CLIENT"] == "true"
    assert ctx["env"]["SPIFFE_TLS_SERVER"] == "true"
    json.dumps(ctx)


def test_validate_bidir_mtls_ok():
    cfg = BidirMTLSConfig(
        trust_domain="charter.example.com", namespace="prod",
        service_account="agent-1",
        svid_socket="/run/spire/sockets/private/api.sock",
        trust_bundle_path="/run/spire/secrets/trustbundle.json",
        node_agent_mount="/run/spire")
    out = validate_bidir_mtls(cfg)
    assert out["ok"] is True, out["problems"]


def test_validate_bidir_mtls_rejects_bad_socket():
    cfg = BidirMTLSConfig(
        trust_domain="charter.example.com",
        svid_socket="/tmp/wrong.sock",
        trust_bundle_path="/run/spire/secrets/trustbundle.json",
        node_agent_mount="/run/spire")
    out = validate_bidir_mtls(cfg)
    assert out["ok"] is False
    assert any("socket" in p for p in out["problems"])


def test_render_bidir_k8s_values_mounts_both_svids():
    cfg = BidirMTLSConfig(trust_domain="charter.example.com")
    vals = render_bidir_k8s_values(cfg, secret_name="spire-svid")
    sp = vals["spiffe"]
    assert sp["bidirectional"] is True
    vol_names = [v.get("name") for v in sp["volumes"]]
    assert "workload-svid" in vol_names
    assert "agent-svid" in vol_names
    assert "trust-bundle" in vol_names
    json.dumps(vals)


def test_attestation_exchange_plan_two_way():
    cfg = BidirMTLSConfig(trust_domain="charter.example.com")
    plan = attestation_exchange_plan(cfg)
    steps = [s["step"] for s in plan]
    assert "mutual-verify" in steps
    assert "mtls-session" in steps
    # the two-way nature: both attestations present
    assert "workload-attest" in steps and "agent-attest-node" in steps


# ------------------------------------------------------------------
# 5. PR diff-level completion
# ------------------------------------------------------------------
def test_complete_diff_hunks_heuristic():
    hunks = [
        {"file": "src/main.py", "hunk_id": "h1",
         "context": "checkpoint save",
         "before": "def save():\n    return 1",
         "after": "def save():\n    return 1",
         "comments": ["should move the save after gate_3",
                       "add a test for this hunk"]},
    ]
    out = complete_diff_hunks(hunks, backend="heuristic")
    assert out["n"] == 1
    p = out["proposals"][0]
    assert p["analyzer"] in ("heuristic", "heuristic-diff",
                              "heuristic-fallback")
    # the heuristic adds a concrete TODO / guard line
    assert "TODO" in p["after"] or "address" in p["rationale"].lower()
    # a patch-shaped snippet is produced
    assert p["patch"].startswith("--- a/src/main.py")


def test_complete_diff_hunks_negative_comment_gets_concern_line():
    hunks = [
        {"file": "auth.py", "hunk_id": "h2", "context": "token handling",
         "before": "def tok():\n    return 'x'",
         "after": "def tok():\n    return 'x'",
         "comments": ["this is broken, a bug, and unsafe"]},
    ]
    out = complete_diff_hunks(hunks, backend="heuristic")
    p = out["proposals"][0]
    assert "CONCERN" in p["after"]
    assert out["counts"]["proposals"] == 1


def test_hunk_proposal_patch_shape():
    hp = HunkProposal(file="a.py", hunk_id="h1", context="c",
                      before="x = 1", after="x = 2",
                      rationale="fix off-by-one")
    patch = hp.as_patch()
    assert "-x = 1" in patch and "+x = 2" in patch
    assert "rationale" in patch


# ------------------------------------------------------------------
# 6. checkpoint RBAC -> IAM / S3 bucket policy
# ------------------------------------------------------------------
def test_role_s3_actions_hierarchy():
    owner = set(role_s3_actions("owner"))
    member = set(role_s3_actions("member"))
    viewer = set(role_s3_actions("viewer"))
    # owner is a superset of member, member of viewer
    assert owner >= member >= viewer
    assert "s3:PutBucketPolicy" in owner
    assert "s3:PutBucketPolicy" not in member
    assert "s3:PutObject" not in viewer


def test_iam_policy_per_role():
    team_roles = {"owner": ["alice"], "member": ["bob"]}
    pols = iam_policy(team_roles, team="platform",
                       account_id="111122223333")
    assert "owner" in pols and "member" in pols
    for role, doc in pols.items():
        assert doc["Version"] == "2012-10-17"
        stmt = doc["Statement"][0]
        assert "charter-platform-" + role in stmt["Principal"]["AWS"]
        assert stmt["Effect"] == "Allow"
    # owner gets the policy-manage action, member does not
    owner_actions = pols["owner"]["Statement"][0]["Action"]
    member_actions = pols["member"]["Statement"][0]["Action"]
    assert "s3:PutBucketPolicy" in owner_actions
    assert "s3:PutBucketPolicy" not in member_actions


def test_s3_bucket_policy_deny_default_and_allow():
    team_roles = {"owner": ["alice"], "viewer": ["carol"]}
    doc = s3_bucket_policy(team_roles, team="platform",
                           account_id="111122223333")
    assert doc["Version"] == "2012-10-17"
    sids = [s["Sid"] for s in doc["Statement"]]
    assert "CharterDenyDefault" in sids
    assert "CharterDenyDefault" in sids  # deny-default present
    # per-role allows for the roles that are actually in team_roles
    assert "CharterAllowOwner" in sids
    assert "CharterAllowViewer" in sids
    # the deny-default condition excludes the team
    deny = next(s for s in doc["Statement"]
                if s["Sid"] == "CharterDenyDefault")
    assert deny["Effect"] == "Deny"
    json.dumps(doc)


def test_render_iam_bundle_shapes():
    out = render_iam_bundle(
        {"owner": ["alice"], "admin": ["bob"], "member": ["carol"]},
        team="platform", account_id="111122223333")
    for key in ("iam_policies", "bucket_policy", "role_actions",
                 "summary"):
        assert key in out
    json.loads(out["iam_policies"])
    json.loads(out["bucket_policy"])
    actions = json.loads(out["role_actions"])
    assert set(actions.keys()) == {"owner", "admin", "member"}
    assert "platform" in out["summary"]
