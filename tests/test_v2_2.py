"""Tests for v2.2 production linkages (online judge, session store, trace link).

All tests run offline (no network / no API key) because:
  - OnlineJudge degrades to the heuristic judge when no key is present
    (assert the *degradation contract*, not the LLM).
  - SessionStore uses the file-backed SQLite + offline hashing embedder.
  - TraceLink.export returns a pending payload when the backend is
    unreachable (assert the *retry-safe contract*).
"""
from __future__ import annotations

import os
import tempfile

from charter import (
    # v2.2 judge
    make_judge, score_with_judge, OfflineJudge, AgnesJudge, OpenAIJudge,
    # v2.2 session store
    SessionStore,
    # v2.2 trace link
    TraceLink, JaegerPush, TempoPush, aggregate_traces, slo_summary,
)
from charter.observability import Span, TraceLogger
from charter import __version__


# ------------------------------------------------------------------
# 1. version
# ------------------------------------------------------------------
def test_version_bumped_v2_2():
    assert __version__.startswith("3.")


# ------------------------------------------------------------------
# 2. llm_judge_online
# ------------------------------------------------------------------
def test_make_judge_offline_when_no_key(monkeypatch):
    for var in ("AGNES_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    jb = make_judge(backend=None)
    assert isinstance(jb, OfflineJudge)
    assert jb.name == "offline"


def test_make_judge_explicit_backends(monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "sk-test")
    jb = make_judge(backend="agnes")
    assert isinstance(jb, AgnesJudge)
    jb2 = make_judge(backend="openai")
    assert isinstance(jb2, OpenAIJudge)


def test_score_with_judge_offline_contract():
    """No key configured -> falls back to the offline heuristic judge,
    no exception, and details flags which judge actually ran."""
    artifacts = {"test_coverage": 0.85, "violations": [],
                 "tests_written": True, "token_ratio": 0.5}
    out = score_with_judge("p1", artifacts, threshold=0.7, online=False)
    assert "scores" in out and "weighted" in out
    assert out["passed"] in (True, False)
    assert out["details"].get("judge") == "offline"


def test_score_with_judge_online_degrades_without_key(monkeypatch):
    """online=True but no key + no network -> graceful offline fallback,
    no exception. This is the contract that keeps CI green offline."""
    for var in ("AGNES_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    artifacts = {"test_coverage": 0.9, "violations": [],
                 "tests_written": True, "token_ratio": 0.4}
    out = score_with_judge("p2", artifacts, threshold=0.7, online=True)
    # OfflineJudge is used -> the judge name is "offline" (neutral fallback),
    # and the result is still well-formed.
    assert out["scores"].get("safety", 0) >= 0
    assert out["weighted"] >= 0
    assert out["details"].get("judge") in ("offline", "offline-fallback")


def test_score_with_judge_heuristic_rewards_good_artifacts():
    good = {"test_coverage": 0.95, "violations": [], "tests_written": True,
            "token_ratio": 0.3}
    bad = {"test_coverage": 0.1, "violations": ["secret leak", "off spec"],
           "tests_written": False, "token_ratio": 0.99}
    g = score_with_judge("g", good, online=False)
    b = score_with_judge("b", bad, online=False)
    assert g["weighted"] > b["weighted"]
    assert g["passed"] is True
    assert b["passed"] is False


def test_offline_judge_never_raises():
    jb = OfflineJudge()
    out = jb.judge("score this: {...}")
    assert "safety" in out["scores"] or "verdict" in out


# ------------------------------------------------------------------
# 3. session_store
# ------------------------------------------------------------------
def test_session_store_remember_and_recall(tmp_path):
    db = str(tmp_path / "s.db")
    ss = SessionStore(path=db)
    ss.open_session("sess-A", "alice", summary="kickoff")
    ss.remember("sess-A", "alice", "Decided to use Postgres for persistence",
                kind="decision", salience=0.9)
    ss.remember("sess-A", "alice", "Ignored a flaky test warning")
    results = ss.recall("alice", "database persistence choice", limit=5)
    assert len(results) >= 1
    top = results[0]
    assert "Postgres" in top["content"] or "persistence" in top["content"].lower()
    assert top["session_id"] == "sess-A"
    assert "similarity" in top and "rank" in top


def test_session_store_cross_session_query(tmp_path):
    db = str(tmp_path / "s2.db")
    ss = SessionStore(path=db)
    ss.open_session("sess-1", "bob")
    ss.open_session("sess-2", "bob")
    ss.remember("sess-1", "bob", "Auth uses JWT with 24h expiry")
    ss.remember("sess-2", "bob", "DB migrations are run via alembic")
    # Cross-session query should surface both sessions for a broad topic
    hits = ss._cross_session("authentication token session", limit=10)
    session_ids = {h["session_id"] for h in hits}
    assert "sess-1" in session_ids or "sess-2" in session_ids
    ss.close()


def test_session_store_persists_across_instances(tmp_path):
    """Open the DB in two separate Store instances -> the second sees the
    first's episodes (true cross-process / cross-session persistence)."""
    db = str(tmp_path / "s3.db")
    ss1 = SessionStore(path=db)
    ss1.open_session("s-A", "carol")
    ss1.remember("s-A", "carol", "Chose the X.509 identity scheme")
    ss1.close()

    ss2 = SessionStore(path=db)
    assert len(ss2.sessions()) == 1
    assert ss2.sessions()[0]["session_id"] == "s-A"
    recalled = ss2.recall("carol", "identity scheme choice", limit=3)
    assert any("X.509" in r["content"] for r in recalled)
    ss2.close()


def test_session_store_recall_scoped_by_session(tmp_path):
    db = str(tmp_path / "s4.db")
    ss = SessionStore(path=db)
    ss.open_session("s1", "dave")
    ss.open_session("s2", "dave")
    ss.remember("s1", "dave", "Topic only in s1: payment gateway")
    ss.remember("s2", "dave", "Topic only in s2: cache invalidation")
    only_s1 = ss.recall("dave", "payment gateway", session_id="s1", limit=5)
    assert all(r["session_id"] == "s1" for r in only_s1)
    ss.close()


# ------------------------------------------------------------------
# 4. trace_link
# ------------------------------------------------------------------
def _make_spans(n=20, with_errors=True):
    logger = TraceLogger(max_spans=200)
    for i in range(n):
        s = logger.log("tool_call",
                       {"tool": "f" if i % 7 else "g", "i": i})
        s.end_ts = s.start_ts + 0.01 * (i + 1)
        if with_errors and i % 5 == 0:
            s.status = "error"
    return logger.spans


def test_aggregate_traces_shapes():
    spans = _make_spans(20)
    agg = aggregate_traces(spans)
    assert agg["total_spans"] == 20
    assert "services" in agg
    svc = list(agg["services"].values())[0]
    for key in ("spans", "errors", "error_rate", "p50_ms", "p95_ms", "rps"):
        assert key in svc
    assert 0.0 <= svc["error_rate"] <= 1.0
    assert svc["p95_ms"] >= svc["p50_ms"] >= 0


def test_slo_summary_met_and_breached():
    spans = _make_spans(20)
    # Generous SLO -> MET
    met = slo_summary(spans, s_lo_ms=5000.0, s_lo_error=0.5)
    assert met["slo_met"] is True
    # Harsh SLO -> BREACHED (error rate 40% > 0.05, or p95 over 100ms)
    breached = slo_summary(spans, s_lo_ms=0.1, s_lo_error=0.01)
    assert breached["slo_met"] is False
    assert breached["summary"] == "BREACHED"


def test_trace_link_export_retry_safe(tmp_path):
    """Point at an unreachable URL -> export() returns a pending payload,
    no exception (retry-safe contract)."""
    link = TraceLink(backend="jaeger",
                     push_url="http://127.0.0.1:1/api/traces")
    spans = _make_spans(5, with_errors=False)
    out = link.export(spans)
    assert out["sent"] == 0
    assert out["pending"] == 5
    assert "body" in out  # payload retained for retry
    assert "error" in out


def test_trace_link_slo_and_digest():
    link = TraceLink(backend="jaeger",
                     push_url="http://127.0.0.1:1/api/traces")
    spans = _make_spans(15)
    digest = link.digest(spans)
    assert digest["total_spans"] == 15
    slo = link.slo(spans, p95_ms=10000.0, error_rate=0.5)
    assert slo["slo_met"] is True


def test_tempo_push_isolated(tmp_path):
    """TempoPush is its own class, and an unreachable Tempo URL is retry-safe."""
    tp = TempoPush(url="http://127.0.0.1:1/v1/traces")
    spans = _make_spans(3, with_errors=False)
    out = tp.push(spans)
    assert out["pending"] == 3 and out["sent"] == 0
