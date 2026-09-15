"""Tests for v2.3 production linkages: mTLS, GitHub PR bot, embed cache, SPIFFE.

All offline-safe: no live network, no real GitHub PR, no LLM key. Each test
asserts the *contract* (degradation / retry-safe / cache-hit behavior) that
keeps CI green with no credentials, while still exercising the real code
path (cert parsing when `cryptography` is present, PR payload prep, cache
hit/miss, SPIFFE grammar + SVID issuance).
"""
from __future__ import annotations

import base64
import json
import os

import pytest

from charter import (
    # v2.3 mTLS
    TrustAnchor, mtls_check, MTLSResult,
    # v2.3 github PR
    TemplatePRBot, open_template_pr, PRResult,
    # v2.3 embed cache
    EmbedCache, CachedEmbedder, production_embedder, embed_with_cache,
    # v2.3 spiffe
    TrustDomain, SVID, build_spiffe_id, parse_spiffe_id,
    issue_svid, verify_svid, SPIFFEError,
)
from charter import __version__
from charter.vector_memory import hash_embed


# ------------------------------------------------------------------
# version
# ------------------------------------------------------------------
def test_version_bumped_v2_3():
    assert __version__.startswith("3.")


# ------------------------------------------------------------------
# mTLS
# ------------------------------------------------------------------
def test_trust_anchor_revocation():
    anchor = TrustAnchor(ca_pem=b"fake-ca", common_name="CA-X")
    assert anchor.is_revoked("abc") is False
    anchor.add_revoked("abc")
    assert anchor.is_revoked("abc") is True


def test_mtls_check_simplified_no_cryptography(monkeypatch):
    """Without cryptography, mTLS falls back to a metadata-blob check; the
    verify contract (expired / revoked / ca-name) still holds."""
    import charter.mtls as m
    monkeypatch.setattr(m, "HAS_CRYPTO", False)
    anchor = TrustAnchor(ca_pem=b"x", common_name="CA")
    now = 0.0
    import time
    far_future = int(time.time()) + 3600
    # craft a "cert" whose PEM contains a charter metadata line
    meta = {"serial": "S1", "not_after": far_future, "ca_name": "CA"}
    cert = b"-----BEGIN CHARTER META CERT-----\n" + json.dumps(meta).encode() + b"\n-----END CHARTER META CERT-----\n"
    ok, reasons = m.verify_chain(cert, anchor)
    # not-after in the future -> valid
    assert ok is True, reasons
    # expired version
    meta2 = dict(meta, not_after=-1)
    cert2 = b"-----BEGIN CHARTER META CERT-----\n" + json.dumps(meta2).encode() + b"\n-----END CHARTER META CERT-----\n"
    ok2, reasons2 = m.verify_chain(cert2, anchor)
    assert ok2 is False and any("expired" in r for r in reasons2)
    # revoked version
    meta3 = dict(meta)
    anchor2 = TrustAnchor(ca_pem=b"x", common_name="CA")
    anchor2.add_revoked("S1")
    ok3, reasons3 = m.verify_chain(cert, anchor2)
    assert ok3 is False and any("revoked" in r for r in reasons3)


def test_mtls_check_both_directions(monkeypatch):
    import charter.mtls as m
    monkeypatch.setattr(m, "HAS_CRYPTO", False)
    anchor = TrustAnchor(ca_pem=b"x", common_name="CA")
    import time
    far_future = int(time.time()) + 3600
    meta_c = {"serial": "C1", "not_after": far_future, "ca_name": "CA"}
    meta_s = {"serial": "S1", "not_after": far_future, "ca_name": "CA"}
    client_cert = b"-----BEGIN CHARTER META CERT-----\n" + json.dumps(meta_c).encode() + b"\n-----END CHARTER META CERT-----\n"
    # server cert PEM must contain the expected hostname for the simplified check
    server_cert = b"-----BEGIN CHARTER META CERT-----\n" + json.dumps(meta_s).encode() + b"\n-----END CHARTER META CERT-----\n"
    server_cert = server_cert + b"\nlocalhost\n"
    res = m.mtls_check(client_cert, server_cert, anchor, server_hostname="localhost")
    assert isinstance(res, MTLSResult)
    assert res.ok is True, res.reasons
    assert res.client_verified and res.server_verified


def test_mtls_check_rejects_bad_hostname(monkeypatch):
    import charter.mtls as m
    monkeypatch.setattr(m, "HAS_CRYPTO", False)
    anchor = TrustAnchor(ca_pem=b"x", common_name="CA")
    meta_c = {"serial": "C1", "not_after": 10**9, "ca_name": "CA"}
    client = b"-----BEGIN CHARTER META CERT-----\n" + json.dumps(meta_c).encode() + b"\n-----END CHARTER META CERT-----\n"
    # server cert with wrong hostname
    server = b"-----BEGIN CHARTER META CERT-----\n" + json.dumps(meta_c).encode() + b"\n-----END CHARTER META CERT-----\n\nexample.com\n"
    res = m.mtls_check(client, server, anchor, server_hostname="not-example.com")
    assert res.ok is False
    assert not res.server_verified


# ------------------------------------------------------------------
# GitHub PR bot (offline: no token -> prepared draft, no exception)
# ------------------------------------------------------------------
_SAMPLE_SPEC = {
    "name": "test-industry",
    "label": "Test Industry",
    "description": "a candidate template",
    "stage_gates": {"stage_0": ["kickoff"]},
    "tdd_enforcement": "soft",
    "token_budget": 100,
    "audit_required_stages": ["stage_0"],
}


def test_open_template_pr_offline_draft(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("TEMPLATE_PR_REPO", raising=False)
    res = open_template_pr(_SAMPLE_SPEC, repo="x/y", token="")
    assert isinstance(res, PRResult)
    assert res.opened is False
    assert res.draft is True
    # payload is fully prepared for a later live apply
    assert res.payload["branch"].startswith("charter/template-test-industry-")
    assert "pr_body" in res.payload
    assert "commit" in res.payload
    assert any("no GITHUB_TOKEN" in e or "no TEMPLATE_PR_REPO" in e
               for e in res.errors)


def test_open_template_pr_rejects_invalid_spec():
    bad = dict(_SAMPLE_SPEC, name="Not A Slug!")
    res = open_template_pr(bad, repo="x/y", token="")
    assert res.opened is False
    assert any("validation" in e for e in res.errors)


def test_template_pr_bot_prepare():
    bot = TemplatePRBot(repo="x/y", token="")
    prepared = bot._prepare(_SAMPLE_SPEC)
    assert prepared["branch"].startswith("charter/template-test-industry-")
    assert prepared["template_path"] == "charter/templates/test-industry.json"
    assert "pr_body" in prepared
    assert "commit" in prepared


# ------------------------------------------------------------------
# Embed cache
# ------------------------------------------------------------------
def test_embed_cache_mem_hit(tmp_path):
    cache = EmbedCache(lru_size=8, disk_path=None)
    key = EmbedCache._key("hash", "hashing", 8, "hello world")
    assert cache.get(key) is None
    vec = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    cache.put(key, "hash", "hashing", 8, vec)
    got = cache.get(key)
    assert got == vec
    stats = cache.stats()
    assert stats["mem_hits"] == 1
    assert stats["disk_enabled"] is False


def test_embed_cache_disk_hit(tmp_path):
    db = str(tmp_path / "embed.db")
    cache = EmbedCache(lru_size=4, disk_path=db)
    key = EmbedCache._key("hash", "hashing", 4, "abc")
    vec = [1.0, 2.0, 3.0, 4.0]
    cache.put(key, "hash", "hashing", 4, vec)
    # Force a second cache instance to hit the disk store only
    cache2 = EmbedCache(lru_size=4, disk_path=db)
    got = cache2.get(key)
    assert got == vec
    assert cache2.stats()["disk_enabled"] is True
    assert cache2.stats()["mem_hits"] == 1  # promoted from disk to mem


def test_cached_embedder_uses_cache():
    cache = EmbedCache(lru_size=8, disk_path=None)
    emb = CachedEmbedder("hash", "hashing", 8, hash_embed, cache)
    v1 = emb("identical text")
    v2 = emb("identical text")
    assert v1 == v2
    assert len(v1) == 8


def test_production_embedder_hash_fallback(monkeypatch):
    for var in ("AGNES_API_KEY", "OPENAI_API_KEY", "EMBED_WHICH"):
        monkeypatch.delenv(var, raising=False)
    emb = production_embedder(which=None, disk_cache=False)
    assert emb.backend == "hash"
    assert callable(emb)
    out = emb("x")
    assert len(out) == emb.dim


def test_embed_with_cache_returns_shape():
    out = embed_with_cache("cache me", which="hash", disk_cache=False)
    for k in ("vector", "dim", "backend", "model", "cache"):
        assert k in out
    assert out["backend"] == "hash"


# ------------------------------------------------------------------
# SPIFFE
# ------------------------------------------------------------------
def test_spiffe_id_grammar():
    sid = build_spiffe_id("charter.example.com", "/ns/prod/sa/agent1")
    assert sid == "spiffe://charter.example.com/ns/prod/sa/agent1"
    parsed = parse_spiffe_id(sid)
    assert parsed["trust_domain"] == "charter.example.com"
    assert parsed["path"] == "/ns/prod/sa/agent1"


def test_spiffe_id_rejects_bad():
    with pytest.raises(SPIFFEError):
        parse_spiffe_id("http://not-a-spiffe")
    with pytest.raises(SPIFFEError):
        build_spiffe_id("Bad_Trust_Domain!")


def test_issue_svid_and_verify(monkeypatch):
    svid = issue_svid("charter.example.com", "/ns/prod/sa/agent1",
                      valid_for_s=3600)
    assert isinstance(svid, SVID)
    assert svid.spiffe_id == "spiffe://charter.example.com/ns/prod/sa/agent1"
    ok, reasons = verify_svid(
        svid.cert_pem, "charter.example.com", svid.spiffe_id)
    assert ok is True, reasons


def test_verify_svid_wrong_trust_domain():
    svid = issue_svid("charter.example.com", "/ns/prod/sa/agent1",
                      valid_for_s=3600)
    ok, reasons = verify_svid(
        svid.cert_pem, "other.example.com", svid.spiffe_id)
    assert ok is False
    assert any("trust domain" in r for r in reasons)


def test_trust_domain_issue_and_bundle():
    td = TrustDomain("charter.example.com", days=1)
    svid = td.issue("/ns/prod/sa/agent1", valid_for_s=60)
    b = td.bundle(svid)
    assert b.svid.spiffe_id == svid.spiffe_id
    exp = b.export()
    assert exp["spiffe_id"] == svid.spiffe_id
    assert exp["ca_cert_count"] >= 0
    # verify round-trips within the same trust domain
    ok, reasons = td.verify(svid)
    assert ok is True, reasons

