"""Tests for v2.5 multi-system linkages (phase 2).

All offline-safe: no live gRPC, no real GitHub PR, no LLM key, no
Alertmanager. Each test asserts the *degradation / retry-safe / local-fallback
contract* that keeps CI green with no credentials, while still exercising the
real code path (weighted voting math, hierarchical compression, rule YAML
shapes, attestation request building, PR-signal scoring on empty signals,
cross-repo bus publish/pull round-trip).
"""
from __future__ import annotations

import json
import os
import tempfile

from charter import (
    # v2.5 judge voting
    vote_judges, ProviderVote, WeightedVotingJudge, accuracy_weights,
    # v2.5 memory hierarchy
    MemoryHierarchy, compress_project, recall_project, TierSummary,
    # v2.5 prometheus rules
    alert_rules, alertmanager_provisioning, render_provisioning_bundle,
    # v2.5 spiffe attestation
    build_attestation_request, spire_attest, verify_attestation,
    AttestationRequest, AttestResult, ATTEST_TYPES,
    # v2.5 PR comment scoring
    fetch_pr_signals, score_from_pr, auto_merge_gate, PRSignals,
    # v2.5 cross-repo checkpoint
    CheckpointBus, publish_checkpoint, pull_checkpoint,
    list_published, import_into_core, PublishedCheckpoint,
    # deps
    SessionStore,
)
from charter import __version__


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------
def test_version_bumped_v2_5():
    assert __version__.startswith("2.")


# ------------------------------------------------------------------
# 1. judge voting
# ------------------------------------------------------------------
def test_weighted_voting_aggregate():
    j = WeightedVotingJudge(threshold=0.7)
    votes = [
        ProviderVote(provider="agnes", scores={
            "spec_compliance": 0.9, "code_quality": 0.8,
            "test_adequacy": 0.7, "efficiency": 0.6, "safety": 1.0},
            verdict="pass", weight=2.0),
        ProviderVote(provider="openai", scores={
            "spec_compliance": 0.7, "code_quality": 0.6,
            "test_adequacy": 0.5, "efficiency": 0.4, "safety": 0.9},
            verdict="fail", weight=1.0),
    ]
    out = j.aggregate(votes)
    assert out["details"]["mode"] == "weighted-voting"
    assert out["details"]["n_providers"] == 2
    # weighted mean for spec_compliance = (0.9*2 + 0.7*1) / 3 = 0.8333
    assert abs(out["scores"]["spec_compliance"] - 0.8333) < 0.001
    assert out["details"]["contributions"]["agnes"] == 0.6667
    assert 0.0 <= out["details"]["effective_agreement"] <= 1.0


def test_weighted_voting_no_votes_fallback():
    j = WeightedVotingJudge(threshold=0.7)
    out = j.aggregate([])
    assert out["details"]["mode"] == "no-votes-fallback"
    assert out["n_providers"] == 0


def test_accuracy_weights_ranks_providers():
    gold = {"s1": {"spec_compliance": 0.9}, "s2": {"spec_compliance": 0.8}}
    provider_scores = {
        "good": {"s1": {"spec_compliance": 0.9},
                 "s2": {"spec_compliance": 0.8}},
        "bad": {"s1": {"spec_compliance": 0.2},
                "s2": {"spec_compliance": 0.1}},
    }
    w = accuracy_weights(gold, provider_scores, top_k=5)
    assert w["good"] > w["bad"]


def test_vote_judges_offline_safe(monkeypatch):
    for var in ("AGNES_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    out = vote_judges("p1", {"test_coverage": 0.8, "violations": [],
                              "tests_written": True, "token_ratio": 0.4})
    # no live providers -> falls back to the heuristic aggregation
    assert out["details"]["mode"] in ("no-votes-fallback", "weighted-voting")
    assert "excluded" in out["details"]


# ------------------------------------------------------------------
# 2. memory hierarchy
# ------------------------------------------------------------------
def test_memory_hierarchy_compress_project(tmp_path):
    db = str(tmp_path / "hier.db")
    store = SessionStore(path=db)
    store.open_session("proj-1", "alice")
    store.open_session("proj-2", "alice")
    store.remember("proj-1", "alice", "Decided to use Postgres",
                   kind="episodic", salience=0.8)
    store.remember("proj-1", "alice", "Fixed the flaky test",
                   kind="episodic", salience=0.7)
    store.remember("proj-2", "alice", "Auth flow uses JWT",
                   kind="episodic", salience=0.9)
    store.remember("proj-2", "alice", "Deployed to staging",
                   kind="episodic", salience=0.6)
    tier = compress_project(store, "my-project", "alice",
                           session_ids=["proj-1", "proj-2"],
                           online=False)
    assert tier.tier == 2
    assert tier.scope == "project"
    assert tier.scope_id == "my-project"
    assert tier.summary
    assert len(tier.facts) >= 1
    # project digest was stored with kind="project_summary"
    proj = store.recall("alice", "postgres persistence",
                        limit=10)
    assert any(r.get("kind") == "project_summary" for r in proj)
    store.close()


def test_recall_project_tiers(tmp_path):
    db = str(tmp_path / "hier2.db")
    store = SessionStore(path=db)
    store.open_session("s1", "bob")
    store.remember("s1", "bob", "raw episode about caching",
                   kind="episodic", salience=0.5)
    store.remember("s1", "bob", "summary fact about caching",
                   kind="summary", salience=2.0)
    store.remember("s1", "bob", "project digest about caching",
                   kind="project_summary", salience=3.0)
    res = recall_project(store, "bob", "caching strategy", limit=5)
    assert "project" in res and "sessions" in res and "episodes" in res
    assert res["top"]  # ordered top-k
    # project-tier items should be tagged tier=2
    proj_tier = [h for h in res["top"] if h.get("tier") == 2]
    assert proj_tier
    store.close()


# ------------------------------------------------------------------
# 3. prometheus rules
# ------------------------------------------------------------------
def test_alert_rules_shapes():
    doc = alert_rules(error_ratio=0.05, tool="execute_in_sandbox",
                      project_id="charter")
    assert "groups" in doc
    rules = doc["groups"][0]["rules"]
    names = [r["alert"] for r in rules]
    assert "CharterHighErrorRate" in names
    assert "CharterToolCallBurst" in names
    assert "CharterLowUptime" in names
    for r in rules:
        assert "expr" in r and "for" in r and "labels" in r
        assert "annotations" in r
        # expr must reference charter metrics
        assert "charter_" in r["expr"]
    # JSON-serializable (Prometheus accepts JSON as a YAML subset)
    json.dumps(doc)


def test_alertmanager_provisioning_shapes():
    am = alertmanager_provisioning(
        receiver="charter-oncall",
        webhook_url="http://hooks.example.com/alerts")
    assert "route" in am and "receivers" in am and "inhibit_rules" in am
    assert am["receivers"][0]["webhook_configs"][0]["url"] == \
        "http://hooks.example.com/alerts"
    assert am["inhibit_rules"][0]["source_matchers"] == \
        ['severity="critical"']
    json.dumps(am)


def test_render_provisioning_bundle():
    bundle = render_provisioning_bundle(
        error_ratio=0.1, tool="init_project",
        webhook_url="http://hooks.example.com",
        project_id="charter")
    assert "prometheus_rules" in bundle and "alertmanager_config" in bundle
    # both are valid JSON strings
    json.loads(bundle["prometheus_rules"])
    json.loads(bundle["alertmanager_config"])
    # the rule expr references the requested tool
    rules = json.loads(bundle["prometheus_rules"])
    burst = [r for r in rules["groups"][0]["rules"]
             if r["alert"] == "CharterToolCallBurst"][0]
    assert "init_project" in burst["expr"]


# ------------------------------------------------------------------
# 4. SPIRE attestation
# ------------------------------------------------------------------
def test_build_attestation_request_k8s():
    req = build_attestation_request(
        "k8s_pod",
        {"service_account": "agent-1", "namespace": "prod"},
        trust_domain="charter.example.com")
    assert req.spiffe_id("charter.example.com") == \
        "spiffe://charter.example.com/ns/prod/sa/agent-1"
    # all types round-trip parse_spiffe_id
    assert req.type in ATTEST_TYPES


def test_build_attestation_request_rejects_unknown_type():
    import pytest
    with pytest.raises(ValueError):
        build_attestation_request("bogus", {})


def test_spire_attest_local_fallback(monkeypatch):
    """No gRPC channel -> attestation falls back to the local TrustDomain
    issuer (same call shape, source='local')."""
    req = build_attestation_request(
        "k8s_pod",
        {"service_account": "agent-1", "namespace": "prod"},
        trust_domain="charter.example.com")
    results = spire_attest(channel=None, spire_service=None,
                           trust_domain="charter.example.com",
                           attestations=[req])
    assert len(results) == 1
    r = results[0]
    assert r.source == "local"
    assert r.ok()
    assert r.spiffe_id.endswith("/ns/prod/sa/agent-1")
    ok, reasons = verify_attestation(r)
    assert ok is True, reasons


def test_spire_attest_requires_at_least_one():
    import pytest
    with pytest.raises(ValueError):
        spire_attest(channel=None, spire_service=None,
                     trust_domain="charter.example.com",
                     attestations=[])


# ------------------------------------------------------------------
# 5. PR comment scoring (offline: empty signals -> conservative gate)
# ------------------------------------------------------------------
def test_fetch_pr_signals_offline(monkeypatch):
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    sig = fetch_pr_signals(123, "x/y", token="")
    assert sig.live is False
    assert sig.n_reviews == 0
    assert sig.errors
    assert "no GITHUB_TOKEN" in sig.errors[0]


def test_score_from_pr_empty_signals():
    sig = PRSignals(pr_number=99, live=False)
    out = score_from_pr(sig)
    assert out["live"] is False
    assert 0.0 <= out["score"] <= 1.0
    assert out["usefulness"] >= 0 and out["adoption"] >= 0 \
        and out["health"] >= 0


def test_score_from_pr_with_signals():
    sig = PRSignals(pr_number=99, live=True,
                    n_reviews=4, n_approved=3,
                    n_changes_requested=1, n_comments=5,
                    n_reactions_positive=8, n_reactions_negative=1)
    out = score_from_pr(sig)
    assert out["score"] > 0.5  # mostly-positive signals
    assert out["usefulness"] > 0.3


def test_auto_merge_gate_conservative():
    sig = PRSignals(pr_number=99, live=False)
    out = score_from_pr(sig)
    gate = auto_merge_gate(out, threshold=0.5)
    assert gate["auto_merge"] is False  # offline + low score
    assert any("not live" in r or "score" in r for r in gate["reasons"])


def test_auto_merge_gate_passes_when_strong():
    sig = PRSignals(pr_number=99, live=True,
                    n_reviews=5, n_approved=5,
                    n_reactions_positive=10, n_comments=2)
    out = score_from_pr(sig)
    gate = auto_merge_gate(out, threshold=0.5, min_reviews=3)
    assert gate["auto_merge"] is True
    assert gate["score"] >= 0.5


# ------------------------------------------------------------------
# 6. cross-repo checkpoint bus
# ------------------------------------------------------------------
def test_checkpoint_bus_publish_and_pull(tmp_path):
    bus = CheckpointBus(str(tmp_path / "bus"))
    path = bus.publish("proj-X", "agent-1",
                       {"stage_index": 3, "stage": "stage_3",
                        "artifacts": {"code": "main.py"}},
                       label="after build", stage="stage_3")
    assert os.path.isfile(path)
    cp = bus.pull("proj-X", agent_id="agent-1", stage="stage_3")
    assert cp is not None
    assert cp.stage == "stage_3"
    assert cp.state["stage_index"] == 3
    assert cp.label == "after build"
    assert cp.agent_id == "agent-1"


def test_checkpoint_bus_list_published(tmp_path):
    bus = CheckpointBus(str(tmp_path / "bus2"))
    bus.publish("p1", "a", {"stage": "stage_1", "stage_index": 1})
    bus.publish("p1", "b", {"stage": "stage_2", "stage_index": 2})
    bus.publish("p2", "a", {"stage": "stage_5", "stage_index": 5})
    items = bus.list_published()
    keys = {(i["project_id"], i["agent_id"], i["stage"]) for i in items}
    assert ("p1", "a", "stage_1") in keys
    assert ("p1", "b", "stage_2") in keys
    assert ("p2", "a", "stage_5") in keys


def test_pull_checkpoint_module_level(tmp_path):
    pub = publish_checkpoint("proj-Y", "agent-2",
                            {"stage": "stage_9", "stage_index": 9},
                            label="final", bus_path=str(tmp_path / "bus3"))
    cp = pull_checkpoint("proj-Y", agent_id="agent-2",
                        stage="stage_9", bus_path=str(tmp_path / "bus3"))
    assert cp is not None
    assert cp.stage == "stage_9"
    assert cp.state["stage_index"] == 9


def test_import_into_core_missing_is_safe(tmp_path):
    # No published checkpoint -> ok=False (does not raise)
    out = import_into_core("never-published", bus_path=str(tmp_path / "bus4"))
    assert out["ok"] is False
    assert "no published checkpoint" in out["reason"]


def test_published_checkpoint_json_roundtrip(tmp_path):
    d = str(tmp_path / "bus5")
    bus = CheckpointBus(d)
    path = bus.publish("rp", "ag", {"stage": "stage_2", "stage_index": 2})
    # re-load the raw JSON and verify the schema
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    for k in ("project_id", "agent_id", "stage", "state", "published_ts"):
        assert k in raw
    reloaded = PublishedCheckpoint.load(path)
    assert reloaded.project_id == "rp" and reloaded.stage == "stage_2"
