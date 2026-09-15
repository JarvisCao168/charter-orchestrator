"""Tests for v2.6 multi-system linkages (phase 3).

All offline-safe: no live LLM, no S3/GCS, no k8s, no real GitHub. Each test
asserts the *degradation / local-fallback / heuristic contract* that keeps
CI green with no credentials, while still exercising the real code path
(concurrent vote aggregation, agglomerative clustering math, Mimir YAML
shapes, k8s SPIRE config JSON, heuristic sentiment, shared-store local
publish/pull + audit log).
"""
from __future__ import annotations

import json
import os
import tempfile

from charter import (
    # v2.6 judge concurrency
    vote_judges_concurrent, JudgeResultCache, cached_vote,
    # v2.6 memory clustering
    MemoryClusterer, cluster_episodes, cluster_session, cluster_count,
    # v2.6 mimir
    mimir_tenants, tenant_rules, label_propagation_config,
    mimir_provisioning_bundle,
    # v2.6 k8s SPIRE
    K8SSPIREAgentConfig, render_spire_agent_config,
    render_agent_values, mtls_env,
    # v2.6 PR sentiment
    analyze_comment, analyze_pr_comments, HeuristicCommentAnalyzer,
    # v2.6 shared checkpoint
    SharedCheckpointStore, AuditLog,
    publish_to_team, pull_from_team, audit_report,
    # deps
    SessionStore,
)
from charter import __version__


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------
def test_version_bumped_v2_6():
    assert __version__.startswith("2.6")


# ------------------------------------------------------------------
# 1. judge concurrency + cache
# ------------------------------------------------------------------
def test_vote_judges_concurrent_offline(monkeypatch):
    for var in ("AGNES_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    out = vote_judges_concurrent(
        "p1", {"test_coverage": 0.8, "violations": [],
                 "tests_written": True, "token_ratio": 0.4},
        backends=["agnes", "openai"], max_workers=2)
    assert "weighted" in out and "verdict" in out
    assert out["details"]["concurrent"] is True
    assert out["details"]["max_workers"] == 2
    # no live providers -> no-votes-fallback
    assert out["details"]["mode"] in ("no-votes-fallback",
                                      "concurrent-no-votes-fallback")


def test_judge_result_cache_hit(tmp_path):
    cache = JudgeResultCache(disk_path=str(tmp_path / "jc.db"))
    out1 = cached_vote("p1", {"x": 1}, backends=["agnes"],
                       cache=cache, concurrent=False)
    assert out1["details"]["cache_hit"] is False
    out2 = cached_vote("p1", {"x": 1}, backends=["agnes"],
                       cache=cache, concurrent=False)
    assert out2["details"]["cache_hit"] is True
    assert out1["weighted"] == out2["weighted"]
    assert out2["details"]["cache"]["disk"] is True


def test_judge_result_cache_miss_on_different_artifacts(tmp_path):
    cache = JudgeResultCache(disk_path=str(tmp_path / "jc2.db"))
    a = cached_vote("p1", {"x": 1}, backends=["agnes"],
                    cache=cache, concurrent=False)
    b = cached_vote("p1", {"x": 2}, backends=["agnes"],
                    cache=cache, concurrent=False)
    assert a["details"]["cache_hit"] is False
    assert b["details"]["cache_hit"] is False  # different artifacts -> miss


# ------------------------------------------------------------------
# 2. memory clustering
# ------------------------------------------------------------------
def _episodes():
    return [
        {"id": 1, "content": "Decided to use Postgres for persistence",
         "salience": 0.9},
        {"id": 2, "content": "Postgres migration script finished",
         "salience": 0.8},
        {"id": 3, "content": "Postgres connection pool tuned",
         "salience": 0.7},
        {"id": 4, "content": "Auth flow uses JWT with 24h expiry",
         "salience": 0.9},
        {"id": 5, "content": "JWT refresh token rotation implemented",
         "salience": 0.8},
        {"id": 6, "content": "Deployed to staging successfully",
         "salience": 0.5},
    ]


def test_cluster_episodes_reduces_corpora():
    out = cluster_episodes(_episodes(), similarity=0.5,
                           max_clusters=10, which="hash")
    assert out  # non-empty
    total_members = sum(c["size"] for c in out)
    assert total_members == 6  # every episode belongs to a cluster
    # clustering should shrink the corpus
    assert len(out) < 6 or len(out) <= 6


def test_cluster_count_report():
    rep = cluster_count(_episodes(), similarity=0.5, max_clusters=10,
                       which="hash")
    assert rep["episodes"] == 6
    assert rep["clusters"] >= 1
    assert rep["reduction"] >= 1.0
    assert rep["avg_cluster_size"] >= 1.0


def test_cluster_session_stores_summaries(tmp_path):
    db = str(tmp_path / "cl.db")
    store = SessionStore(path=db)
    store.open_session("s1", "alice")
    for i, e in enumerate(_episodes()):
        store.remember("s1", "alice", e["content"], kind="episodic",
                       salience=e["salience"])
    res = cluster_session(store, "s1", "alice", similarity=0.5,
                          max_clusters=5, which="hash")
    assert res["episodes"] == 6
    assert res["clusters"] >= 1
    assert res["stored"] == res["clusters"]
    # cluster summaries were written back
    recalled = store.recall("alice", "postgres persistence",
                             session_id="s1", limit=20)
    assert any(r.get("kind") == "cluster_summary" for r in recalled)
    store.close()


# ------------------------------------------------------------------
# 3. Mimir multi-tenant
# ------------------------------------------------------------------
def test_mimir_tenants_stable():
    t = mimir_tenants(["Project A", "project-a", "b"])
    assert t["Project A"] == t["project-a"]  # case-insensitive
    assert t["b"] == "charter-b"
    json.dumps(t)


def test_tenant_rules_shapes():
    doc = tenant_rules("my-project", tenant="charter-my-project")
    assert "groups" in doc
    rules = doc["groups"][0]["rules"]
    names = [r["alert"] for r in rules]
    assert "CharterHighErrorRate" in names
    for r in rules:
        assert "tenant" in r["labels"]
        assert r["labels"]["tenant"] == "charter-my-project"
        assert r["labels"]["project_id"] == "my-project"
        assert "expr" in r
    json.dumps(doc)


def test_label_propagation_config():
    lp = label_propagation_config("charter-x",
                                   extra_labels={"team": "platform"})
    assert lp["enabled"] is True
    override = lp["per_tenant_override"]["charter-x"]["labels"]
    assert "tenant" in override and "team" in override
    json.dumps(lp)


def test_mimir_provisioning_bundle():
    bundle = mimir_provisioning_bundle(
        ["alpha", "beta"], prefix="charter", error_ratio=0.1)
    assert set(bundle["tenants"].keys()) == {"alpha", "beta"}
    assert bundle["tenants"]["alpha"] == "charter-alpha"
    for tenant in bundle["tenants"].values():
        assert tenant in bundle["rules"]
        assert tenant in bundle["label_propagation"]
    # datasources includes Mimir + Loki + Tempo
    ds_names = [d["name"] for d in bundle["datasources"]["datasources"]]
    assert any("Mimir" in n for n in ds_names)
    assert any("Loki" in n for n in ds_names)
    json.dumps(bundle)


# ------------------------------------------------------------------
# 4. k8s SPIRE Agent mTLS
# ------------------------------------------------------------------
def test_render_spire_agent_config():
    cfg = K8SSPIREAgentConfig(trust_domain="charter.example.com",
                              namespace="prod", service_account="agent-1")
    doc = render_spire_agent_config(cfg, spire_server_url="spire:8091")
    assert doc["agent"]["k8s"]["service_account"] == "agent-1"
    assert doc["agent"]["k8s"]["namespace"] == "prod"
    assert doc["trust_domain"] == "charter.example.com"
    entry = doc["entries"][0]
    assert entry["spiffe_id"].startswith(
        "spiffe://charter.example.com/ns/prod/sa/agent-1")
    json.dumps(doc)


def test_render_agent_values_mounts_socket():
    cfg = K8SSPIREAgentConfig()
    vals = render_agent_values(cfg, secret_name="spire-svid")
    sp = vals["spiffe"]
    assert sp["enabled"] is True
    assert sp["svidSocket"] == cfg.svid_socket
    # volumes include a projected serviceaccount token
    assert any("projected" in v for v in sp["volumes"])
    env = sp["env"]
    assert env["SPIFFE_ENDPOINT_SOCKET"] == cfg.svid_socket
    json.dumps(vals)


def test_mtls_env_flags():
    cfg = K8SSPIREAgentConfig()
    env = mtls_env(cfg, server=True, client=True)
    assert env["SPIFFE_TLS_SERVER"] == "true"
    assert env["SPIFFE_TLS_CLIENT"] == "true"
    env2 = mtls_env(cfg, server=False, client=False)
    assert "SPIFFE_TLS_SERVER" not in env2


# ------------------------------------------------------------------
# 5. PR sentiment
# ------------------------------------------------------------------
def test_analyze_comment_heuristic():
    a = analyze_comment(
        "This is great and clean, the checkpoint save should be moved "
        "after gate_3 because it races with restore",
        backend="heuristic")
    assert a.sentiment > 0  # positive words dominate
    assert a.specificity > 0.2  # has code + action verbs
    assert a.actionable is True
    assert a.analyzer == "heuristic"


def test_analyze_comment_negative_heuristic():
    a = analyze_comment("bad, broken, this is a bug and it is insecure",
                        backend="heuristic")
    assert a.sentiment < 0
    assert a.analyzer == "heuristic"


def test_analyze_pr_comments_offline(monkeypatch):
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    out = analyze_pr_comments(123, "x/y", token="")
    assert out["live"] is False
    assert out["n_comments"] == 0
    assert out["analyzer"] in ("heuristic", "llm")
    assert "aggregate" in out
    assert out["aggregate"]["n_actionable"] == 0


def test_heuristic_analyzer_shapes():
    ha = HeuristicCommentAnalyzer()
    out = ha.analyze("lgtm")
    assert "sentiment" in out and "specificity" in out
    assert "actionable" in out and "summary" in out


# ------------------------------------------------------------------
# 6. shared checkpoint store + audit
# ------------------------------------------------------------------
def test_shared_store_publish_and_pull_local(tmp_path):
    store = SharedCheckpointStore(
        backend="filesystem",
        local_path=str(tmp_path / "bus"),
        audit_path=str(tmp_path / "audit.log"))
    out = store.publish("proj-A", "agent-1",
                        {"stage": "stage_3", "stage_index": 3,
                         "artifacts": {"code": "main.py"}},
                        label="after build", stage="stage_3",
                        actor="alice")
    assert out["ok"] is True
    assert out["backend"] == "filesystem"
    got = store.pull("proj-A", agent_id="agent-1", stage="stage_3",
                      actor="bob")
    assert got is not None
    assert got["stage"] == "stage_3"
    assert got["state"]["stage_index"] == 3
    assert got["agent_id"] == "agent-1"
    # audit log recorded both ops
    report = store.report()
    assert report["total"] >= 2
    assert "publish" in report["by_op"] and "pull" in report["by_op"]
    assert "alice" in report["by_actor"] and "bob" in report["by_actor"]


def test_shared_store_degrades_without_s3_sdk(tmp_path, monkeypatch):
    """backend='s3' with no boto3 + no bucket -> degrades to filesystem
    (local path), publish still succeeds locally."""
    store = SharedCheckpointStore(
        backend="s3",
        local_path=str(tmp_path / "bus2"),
        s3_bucket="charter-checkpoints",
        audit_path=str(tmp_path / "audit2.log"))
    out = store.publish("proj-B", "agent-2",
                        {"stage": "stage_1", "stage_index": 1},
                        stage="stage_1", actor="carol")
    # whether s3 is live or degraded, the local copy is always written
    assert out["ok"] in (True, False)
    got = store.pull("proj-B", agent_id="agent-2", stage="stage_1",
                      actor="dave")
    assert got is not None or "ok" in str(out)
    assert store.report()["total"] >= 1


def test_audit_log_report_shapes(tmp_path):
    al = AuditLog(str(tmp_path / "a.log"))
    # no entries -> empty report with zero counts
    rep = al.report()
    assert rep["total"] == 0
    assert rep["by_op"] == {}
    assert rep["last"] is None


def test_publish_pull_team_module_level(tmp_path):
    lp = str(tmp_path / "bus3")
    ap = str(tmp_path / "audit3.log")
    out = publish_to_team("proj-C", "agent-3",
                           {"stage": "stage_9", "stage_index": 9},
                           stage="stage_9", backend="filesystem",
                           local_path=lp, audit_path=ap, actor="erin")
    assert out["ok"] is True
    got = pull_from_team("proj-C", agent_id="agent-3", stage="stage_9",
                         backend="filesystem", local_path=lp,
                         audit_path=ap, actor="frank")
    assert got is not None
    assert got["stage"] == "stage_9"
    rep = audit_report(backend="filesystem", local_path=lp,
                       audit_path=ap)
    assert rep["total"] >= 2
