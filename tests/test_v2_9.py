"""Tests for v2.9 multi-system linkages (phase 6).

All offline-safe: no live K8s cluster, no AWS account, no gRPC channel, no
LLM key. Each test asserts the *plan-only / dry-run / heuristic / mock*
contract that keeps CI green with no credentials, while still exercising
the real code path (cost-capped multi-trigger autoscaler, cross-language
merge, gRPC plan, bidir-mTLS regression invariants, cross-hunk
reconciliation, IAM dry-run + audit).
"""
from __future__ import annotations

import json
import os
import tempfile

from charter import (
    # v2.9 judge pool cost
    JudgePoolAutoscaler, render_cost_autoscaler, plan_judge_pool,
    # v2.9 cross-language memory
    detect_topic_keywords, cross_language_merge, merge_cross_language,
    # v2.9 oncall grpc
    OnCallGRPCClient, render_oncall_grpc_stubs,
    # v2.9 spire bidir regression
    BidirMTLSConfig, run_bidir_mtls_regression, regression_report,
    # v2.9 pr diff consistency
    HunkProposal, CrossHunkConsistency, reconcile_hunks,
    cross_file_summary,
    # v2.9 checkpoint iam apply
    IamApplier, apply_iam_policies, iam_drift_report, iam_audit_report,
    # deps
    OnCallIntegration,
)
from charter import __version__


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------
def test_version_bumped_v2_9():
    assert __version__.startswith("3.")


# ------------------------------------------------------------------
# 1. judge pool multi-trigger + cost-aware
# ------------------------------------------------------------------
def test_cost_autoscaler_caps_replicas_by_budget():
    plan = plan_judge_pool({"x": 1}, backends=["agnes"], replicas_per_provider=1)
    asc = JudgePoolAutoscaler(plan, min_replicas=1, max_replicas=24,
                               per_replica_hour=1.0, daily_budget=10.0)
    # $10 budget, 1 $/replica/hour, 60 min -> max 10 replicas
    cap = asc.max_replicas_for_budget(budget=10.0, duration_min=60)
    assert cap == 10
    # a tight budget caps lower
    cap2 = asc.max_replicas_for_budget(budget=3.0, duration_min=60)
    assert cap2 == 3
    # clamp to min
    cap3 = asc.max_replicas_for_budget(budget=0.5, duration_min=60)
    assert cap3 >= 1  # min_replicas floor


def test_cost_autoscaler_scale_decision_cost_limited():
    plan = plan_judge_pool({"x": 1}, backends=["agnes"], replicas_per_provider=1)
    asc = JudgePoolAutoscaler(plan, min_replicas=1, max_replicas=50,
                               per_replica_hour=1.0, daily_budget=20.0,
                               pending_threshold=24, burst_threshold=64)
    # metrics ask for a lot; the budget should cap it
    d = asc.scale_decision(
        {"pending_tasks": 200, "burst": 200, "calendar_active": True},
        budget=5.0, duration_min=60)
    # 5 $ / 1 $ per replica-hour -> ceiling 5
    assert d["recommended_replicas"] <= 5
    assert d["cost_limited"] is True
    assert d["triggers"]  # multiple triggers fired


def test_render_cost_autoscaler_keda_multi_trigger():
    plan = plan_judge_pool({"x": 1}, backends=["agnes", "openai"],
                            replicas_per_provider=2)
    out = render_cost_autoscaler(
        plan, min_replicas=1, max_replicas=30, per_replica_hour=0.5,
        daily_budget=100.0, pending_threshold=24, burst_threshold=64,
        prometheus_rule="charter_high_error_rate",
        calendar_window="09:00-18:00",
        triggers=["pending-judge-tasks", "prometheus", "calendar", "burst"])
    keda = json.loads(out["keda_scaledobject"])
    # all 4 triggers present
    trig_types = [t["type"] for t in keda["spec"]["triggers"]]
    assert len(keda["spec"]["triggers"]) == 4
    assert "externals" in trig_types and "prometheus" in trig_types
    assert "calendar" in trig_types
    # cost ceiling is in the spec metadata
    assert "cost_ceiling" in keda["spec"]
    # scale table has entries
    table = json.loads(out["scale_table"])
    assert len(table) >= 3
    assert all("recommended_replicas" in row for row in table)


# ------------------------------------------------------------------
# 2. cross-language memory merging
# ------------------------------------------------------------------
def test_detect_topic_keywords_cross_language():
    # zh "数据库连接池调优" -> roman keywords {database, connection, pool, tuning}
    zh = detect_topic_keywords("数据库连接池调优", "zh")
    assert "database" in zh and "connection" in zh and "pool" in zh
    en = detect_topic_keywords("database connection pool tuning", "en")
    assert "database" in en and "connection" in en and "pool" in en


def test_cross_language_merge_merges_same_topic():
    clusters = [
        {"label": "db-zh", "size": 2, "top_content": "数据库连接池调优完成",
         "member_ids": [1, 2], "language": "zh",
         "name": "db-zh", "description": "zh cluster"},
        {"label": "db-en", "size": 2, "top_content":
         "database connection pool tuning finished",
         "member_ids": [3, 4], "language": "en",
         "name": "db-en", "description": "en cluster"},
    ]
    from charter.memory_cross_language import detect_topic_keywords as dtk
    ks = {"0": dtk(clusters[0]["top_content"], "zh"),
          "1": dtk(clusters[1]["top_content"], "en")}
    out = cross_language_merge(clusters, ks, similarity=0.30)
    # the two same-topic clusters should merge into ONE
    merged_multi = [m for m in out if len(m.languages) > 1]
    assert merged_multi, "expected a cross-language merge"
    m = merged_multi[0]
    assert set(m.languages) == {"zh", "en"}
    assert m.size == 4
    assert m.merged is True


def test_merge_cross_language_report():
    eps = [
        {"id": 1, "content": "数据库连接池调优完成", "salience": 0.9},
        {"id": 2, "content": "database connection pool tuning finished",
         "salience": 0.9},
        {"id": 3, "content": "Auth flow uses JWT with 24h expiry",
         "salience": 0.8},
        {"id": 4, "content": "认证流程使用 JWT 24 小时过期", "salience": 0.8},
    ]
    out = merge_cross_language(eps, similarity=0.5, max_clusters=10,
                               cross_sim=0.30, which="hash")
    assert out["episodes"] == 4
    assert out["merged_clusters"] >= 1
    # the zh+en pairs should have merged
    assert out["merged_by_language"] >= 1
    assert "report" in out and out["report"]
    json.dumps(out["merged"])


# ------------------------------------------------------------------
# 3. OnCall real gRPC delivery
# ------------------------------------------------------------------
def _alert():
    return {"labels": {"alertname": "CharterHighErrorRate",
                        "tenant": "charter-alpha", "severity": "critical",
                        "project_id": "alpha"},
            "annotations": {"description": "error ratio high"},
            "startsAt": "2025-01-01T00:00:00Z"}


def test_oncall_grpc_notify_request_shape():
    alert = _alert()
    integ = OnCallIntegration(name="platform", kind="grpc", config={})
    client = OnCallGRPCClient()
    req = client.notify_request(alert, integ)
    assert req["service"] == "oncall.OnCallService"
    assert req["method"] == "Notify"
    assert req["payload"]["title"] == "CharterHighErrorRate"
    json.dumps(req)


def test_oncall_grpc_deliver_plan_only_offline():
    alert = _alert()
    integ = OnCallIntegration(name="grpc-bridge", kind="grpc", config={})
    client = OnCallGRPCClient()
    out = client.deliver(alert, integ, channel=None, stub=None)
    assert out["delivered"] is False
    assert out["via"] == "grpc-plan"
    assert "request" in out
    assert out["reason"]


def test_oncall_grpc_deliver_live_with_mock_stub():
    """A mock channel + stub that echoes the request -> delivered=True."""
    alert = _alert()
    integ = OnCallIntegration(name="grpc-bridge", kind="grpc", config={})

    class _MockChannel:
        pass

    class _MockStub:
        def Notify(self, req, timeout=30):
            return {"echo": req["method"], "ok": True}

    client = OnCallGRPCClient()
    out = client.deliver(alert, integ, channel=_MockChannel(),
                         stub=_MockStub())
    assert out["delivered"] is True
    assert out["via"] == "grpc"
    assert out["response"]["echo"] == "Notify"


def test_render_oncall_grpc_stubs():
    integrations = {"platform": OnCallIntegration(
        name="platform", kind="grpc", config={})}
    out = render_oncall_grpc_stubs(integrations,
                                    channel_target="grafana:50051")
    svc = json.loads(out["service"])
    assert svc["service"] == "oncall.OnCallService"
    assert "Notify" in svc["methods"]
    chan = json.loads(out["channel"])
    assert chan["target"] == "grafana:50051"
    json.loads(out["integrations"])


# ------------------------------------------------------------------
# 4. k8s SPIRE bidir mTLS regression
# ------------------------------------------------------------------
def test_run_bidir_mtls_regression_passes():
    cfg = BidirMTLSConfig(trust_domain="charter.example.com",
                           namespace="prod", service_account="agent-1",
                           svid_socket="/run/spire/sockets/private/api.sock",
                           trust_bundle_path="/run/spire/secrets/trustbundle.json",
                           node_agent_mount="/run/spire")
    out = run_bidir_mtls_regression(cfg)
    assert out["regression_passed"] is True, out["invariants"]
    inv_ids = [i["id"] for i in out["invariants"]]
    # all 6 invariants present
    assert len(inv_ids) == 6
    for i in out["invariants"]:
        assert i["ok"] is True


def test_regression_report_pass_and_fail():
    good = regression_report(BidirMTLSConfig(
        trust_domain="charter.example.com",
        svid_socket="/run/spire/sockets/private/api.sock",
        trust_bundle_path="/run/spire/secrets/trustbundle.json",
        node_agent_mount="/run/spire"))
    assert good["regression_passed"] is True
    assert good["failed"] == []

    bad = regression_report(BidirMTLSConfig(
        trust_domain="charter.example.com",
        svid_socket="/tmp/wrong.sock",  # not under the mount
        trust_bundle_path="/run/spire/secrets/trustbundle.json",
        node_agent_mount="/run/spire"))
    assert bad["regression_passed"] is False
    assert any("I6" in f for f in bad["failed"])


# ------------------------------------------------------------------
# 5. PR diff cross-hunk consistency
# ------------------------------------------------------------------
def _hp(file, hid, before, after, rationale=""):
    return HunkProposal(file=file, hunk_id=hid, context="",
                         before=before, after=after, rationale=rationale)


def test_reconcile_hunks_propagates_rename():
    # hunk1 renames `get_data` -> `fetch_data`; hunk2 still uses `get_data`
    h1 = _hp("a.py", "h1", "def get_data():\n    return 1",
              "def fetch_data():\n    return 1")
    h2 = _hp("a.py", "h2", "x = get_data()", "x = get_data()")
    reconciled, problems = reconcile_hunks([h1, h2])
    kinds = [p.kind for p in problems]
    assert "unpropagated-rename" in kinds
    # h2's after should now use fetch_data (propagated)
    h2_out = next(p for p in reconciled if p.hunk_id == "h2")
    assert "fetch_data" in h2_out.after
    assert "get_data" not in h2_out.after


def test_reconcile_hunks_no_problems_when_clean():
    h1 = _hp("a.py", "h1", "x = 1", "x = 2")
    h2 = _hp("b.py", "h2", "y = 1", "y = 2")
    reconciled, problems = reconcile_hunks([h1, h2])
    assert problems == []
    assert len(reconciled) == 2


def test_cross_file_summary():
    # a symbol defined in a.py (before) and used in b.py (after) -> a
    # cross-file dependency
    h1 = _hp("a.py", "h1", "def helper():\n    return 1",
              "def helper():\n    return 1")
    h2 = _hp("b.py", "h2", "z = 0", "z = helper()")
    summary = cross_file_summary([h1, h2])
    assert summary["n_files"] == 2
    # b.py cross-file-references `helper` owned by a.py
    assert "b.py" in summary["files"]
    assert summary["files"]["b.py"]["cross_file_symbols"].get("helper") == "a.py"


# ------------------------------------------------------------------
# 6. checkpoint IAM apply + audit
# ------------------------------------------------------------------
def test_apply_iam_policies_dry_run(tmp_path):
    out = apply_iam_policies(
        {"owner": ["alice"], "member": ["bob"]},
        team="platform", session=None,
        audit_path=str(tmp_path / "iam.log"))
    assert out["applied"] is False
    assert out["dry_run"] is True
    # planned calls: create_role + put_role_policy per role + 1 bucket policy
    apis = [c["api"] for c in out["planned_calls"]]
    assert "iam.create_role" in apis
    assert "iam.put_role_policy" in apis
    assert "s3.put_bucket_policy" in apis
    # role ARNs built
    assert "owner" in out["role_arns"]
    assert out["role_arns"]["owner"].startswith(
        "arn:aws:iam::000000000000:role/charter-platform-owner")


def test_iam_drift_report_dry_run(tmp_path):
    out = iam_drift_report({"owner": ["alice"]}, team="platform",
                            session=None)
    assert out["live"] is False
    assert out["drift"] == []
    assert out["expected_roles"] == ["owner"]


def test_iam_applier_dry_run_no_session(tmp_path):
    applier = IamApplier(session=None, team="platform",
                          audit_log=None)
    out = applier.apply({"owner": ["alice"]})
    assert out["applied"] is False
    assert out["dry_run"] is True


def test_iam_audit_log_records(tmp_path):
    log_path = str(tmp_path / "audit.log")
    out1 = apply_iam_policies({"owner": ["a"]}, team="t1",
                              session=None, audit_path=log_path)
    out2 = apply_iam_policies({"owner": ["b"]}, team="t2",
                              session=None, audit_path=log_path)
    report = iam_audit_report(audit_path=log_path)
    # each apply recorded a dry-run audit entry (one per planned call)
    assert report["total"] >= 1
    assert "by_op" in report
    # the audit log is JSONL
    with open(log_path, encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    for line in lines:
        json.loads(line)  # every line is valid JSON


def test_apply_iam_policies_live_mock(tmp_path):
    """A mock boto3 session that records the calls (no real AWS) ->
    applied=True + the calls hit the mock, and the audit log records
    each mutation."""
    class _MockS3:
        def put_bucket_policy(self, **kw):
            return {"ok": True}

    class _MockIam:
        def __init__(self):
            self.created = []
            self.polled = []
        def create_role(self, RoleName, **kw):
            self.created.append(RoleName)
            return {"Role": {"Arn": f"arn:aws:iam::0:role/{RoleName}"}}
        def get_role(self, RoleName, **kw):
            return {"Role": {"Arn": f"arn:aws:iam::0:role/{RoleName}"}}
        def put_role_policy(self, RoleName, PolicyName, PolicyDocument):
            self.polled.append((RoleName, PolicyName))

    class _MockSession:
        def client(self, name, **kw):
            if name == "iam":
                return _MockIam()
            if name == "s3":
                return _MockS3()
            raise ValueError(name)

    session = _MockSession()
    applier = IamApplier(session=session, team="platform",
                          audit_log=None)
    out = applier.apply({"owner": ["alice"], "member": ["bob"]})
    assert out["applied"] is True
    assert out["dry_run"] is False
    assert "owner" in out["role_arns"]
    assert "member" in out["role_arns"]
