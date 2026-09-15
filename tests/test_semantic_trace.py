"""Tests for charter/semantic_trace (v3.11 semantic tracing + hallucination guard)."""
from __future__ import annotations

import charter.semantic_trace as st


def test_cosine_similarity_identical():
    assert abs(st.cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal():
    assert abs(st.cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_similarity_opposite():
    assert abs(st.cosine_similarity([1.0, 1.0], [-1.0, -1.0]) + 1.0) < 1e-9


def test_cosine_similarity_empty():
    assert st.cosine_similarity([], [1.0, 2.0]) == 0.0


def test_make_embedder_offline_fallback():
    emb = st.make_embedder(provider="null", dim=128)
    vec = emb("hello world", 128)
    assert isinstance(vec, list) and len(vec) == 128
    # deterministic
    assert emb("hello world", 128) == vec


def test_tracer_records_similar_vs_unrelated():
    t = st.SemanticTracer(threshold=0.5, dim=128)
    sim = t.record("a", "query the stock price of AAPL", "the stock price of AAPL is 182")
    unrel = t.record("b", "query the stock price of AAPL", "the weather is nice today")
    # similar pair should score higher than an unrelated pair
    assert sim.similarity > unrel.similarity
    # the unrelated one falls below threshold -> hallucination
    assert unrel.verdict == st.TraceVerdict.HALLUCINATION


def test_tracer_guard_intercepts_hallucination():
    t = st.SemanticTracer(threshold=0.5, dim=128)
    span = t.record("x", "query the stock price of AAPL", "lorem ipsum dolor sit amet")
    verdict = t.guard(span)
    assert verdict["allowed"] is False
    assert verdict["verdict"] == st.TraceVerdict.HALLUCINATION


def test_tracer_guard_allows_ok_span():
    t = st.SemanticTracer(threshold=0.0, dim=128)
    span = t.record("y", "query the stock price of AAPL", "the stock price of AAPL is 182")
    verdict = t.guard(span)
    assert verdict["allowed"] is True


def test_tracer_hallucination_aggregate():
    t = st.SemanticTracer(threshold=0.5, dim=128)
    t.record("1", "query the stock price of AAPL", "lorem ipsum dolor sit amet")
    t.record("2", "query the stock price of AAPL", "the stock price of AAPL is 182")
    assert len(t.hallucinations()) == 1
    s = t.summary()
    assert s["spans"] == 2 and s["hallucinations"] == 1
