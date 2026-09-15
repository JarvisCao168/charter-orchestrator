"""v2.1 tests: real Grafana provisioning, X.509/mTLS, LLM embedder, template PR flow.

X.509 tests are skipped if `cryptography` is not installed (CI-safe); the HMAC
identity in charter/identity.py remains the always-available path.
"""
import os
import sys
import json
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# ---------------------------------------------------------------------------
# 1) Real Grafana / Prometheus provisioning
# ---------------------------------------------------------------------------
from charter.grafana import (
    prometheus_data_source, tempo_data_source, dashboard_json,
    prometheus_scrape_config, otlp_exporter_config, live_metrics_demo,
)


def test_prometheus_datasource_provisioning():
    ds = prometheus_data_source(url="http://prom:9090")
    assert ds["apiVersion"] == 1
    assert ds["datasources"][0]["type"] == "prometheus"
    assert ds["datasources"][0]["url"] == "http://prom:9090"


def test_tempo_datasource():
    ds = tempo_data_source(url="http://tempo:3200")
    assert ds["datasources"][0]["type"] == "tempo"


def test_dashboard_wires_both_datasources():
    dash = dashboard_json(project_id="p1", ds_prom="P", ds_tempo="T")
    types = [p["type"] for p in dash["panels"]]
    assert "timeseries" in types and "stat" in types and "traces" in types
    # timeseries/stat panels point at prometheus ds, traces at tempo ds
    traces = [p for p in dash["panels"] if p["type"] == "traces"][0]
    assert traces["targets"][0]["datasource"] == "T"


def test_scrape_and_otlp_configs():
    sc = prometheus_scrape_config(service="charter", port=9105)
    assert sc["scrape_configs"][0]["static_configs"][0]["targets"] == ["charter:9105"]
    oc = otlp_exporter_config()
    assert oc["protocol"] == "http/protobuf"


def test_live_metrics_demo_bundle():
    bundle = live_metrics_demo()
    for key in ["prometheus_ds", "tempo_ds", "dashboard",
                "prometheus_scrape", "otlp_exporter", "current_prometheus_text"]:
        assert key in bundle, key
    assert "charter_spans_total" in bundle["current_prometheus_text"]


# ---------------------------------------------------------------------------
# 2) X.509 agent certs + mTLS-style signed calls (skipped without cryptography)
# ---------------------------------------------------------------------------
try:
    import cryptography  # noqa: F401
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography not installed")
def test_x509_issue_and_sign_verify():
    from charter import x509_issue, x509_sign, x509_verify
    cert = x509_issue("agent-x", ["execute_in_sandbox"])
    call = x509_sign("agent-x", "execute_in_sandbox", {"cmd": "pytest"})
    ok = x509_verify(call, {"cmd": "pytest"})
    assert ok["ok"], ok
    # tampered payload must fail
    bad = x509_verify(call, {"cmd": "other"})
    assert not bad["ok"] and "payload digest mismatch" in bad["problems"]


@pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography not installed")
def test_x509_replay_and_capability():
    from charter import x509_issue, x509_sign, x509_verify
    x509_issue("agent-y", ["read_only"])
    # capability violation
    with pytest.raises(PermissionError):
        x509_sign("agent-y", "delete_db", {})
    call = x509_sign("agent-y", "read_only", {"q": 1})
    assert x509_verify(call, {"q": 1})["ok"]
    assert not x509_verify(call, {"q": 1})["ok"]  # replay


@pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography not installed")
def test_x509_cert_is_real_x509():
    from charter import x509_issue
    from cryptography import x509 as cx
    from cryptography.hazmat.primitives import serialization
    cert = x509_issue("agent-z", ["a"])
    loaded = cx.load_pem_x509_certificate(cert.cert_pem)
    attrs = loaded.subject.get_attributes_for_oid(
        cx.oid.NameOID.COMMON_NAME)
    assert attrs and attrs[0].value == "agent-z"
    # loadable private key = PKCS8
    key = serialization.load_pem_private_key(cert.key_pem, password=None)
    assert key is not None


# ---------------------------------------------------------------------------
# 3) LLM embedder backends (offline-safe: no network in tests)
# ---------------------------------------------------------------------------
from charter.llm_embed import (
    NullEmbedder, pick_embedder, _HttpEmbedder,
)


def test_null_embedder_raises():
    e = NullEmbedder()
    with pytest.raises(RuntimeError):
        e("hello")


def test_pick_embedder_null():
    e = pick_embedder("null")
    assert isinstance(e, NullEmbedder)


def test_http_embedder_shaping(monkeypatch):
    """_HttpEmbedder must normalize + L2-normalize vectors; no real network."""
    eb = _HttpEmbedder("key", "http://fake/embed", "m", dim=4)

    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["sent"] = json.loads(req.data.decode())
        class R:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return json.dumps({"data": [{"embedding": [0.0, 0.0, 0.0]}]}).encode()
        return R()
    monkeypatch.setattr("charter.llm_embed.urllib.request.urlopen", fake_urlopen)
    vec = eb("cache layer choice")
    assert len(vec) == 4                      # padded to dim
    assert captured["sent"]["dimensions"] == 4  # dim requested upstream


def test_pick_embedder_no_key_raises(monkeypatch):
    """pick_embedder('openai') must raise when no OPENAI_API_KEY is available.

    monkeypatch ensures this test is deterministic in any environment,
    including CI runners that always inject GITHUB_TOKEN.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    import pytest as _p
    with _p.raises(ValueError):
        pick_embedder("openai")


# ---------------------------------------------------------------------------
# 4) Template marketplace PR flow
# ---------------------------------------------------------------------------
from charter.template_pr import (
    TemplateMarketplace, validate_template, render_pr, TemplateSpecError,
)


def _good_spec(name="logistics"):
    return {
        "name": name, "label": "Logistics / Supply Chain",
        "stage_gates": {"stage_8": ["release_checklist", "logistics_audit"]},
        "tdd_enforcement": "soft", "token_budget": 90000,
        "guardrail_extra_patterns": [r"(?i)dangerous\s+drive"],
        "audit_required_stages": ["stage_8"],
    }


def test_validate_good_spec_clean():
    assert validate_template(_good_spec()) == []


def test_validate_bad_specs():
    spec = _good_spec()
    spec["name"] = "Bad Name!"          # not a slug
    spec["stage_gates"] = {"stage_99": []}   # unknown stage
    spec["tdd_enforcement"] = "yolo"      # invalid
    probs = validate_template(spec)
    assert any("slug" in p for p in probs)
    assert any("unknown stage" in p for p in probs)
    assert any("yolo" in p for p in probs)


def test_marketplace_full_lifecycle():
    m = TemplateMarketplace()
    pr = m.propose(_good_spec(), author="community-alice")
    assert pr.pr_id and pr.status == "open"
    m.approve(pr.pr_id, "reviewer-1")
    merged = m.merge(pr.pr_id)
    assert merged == "logistics"
    assert "logistics" in m.names()
    assert m.load("logistics")["token_budget"] == 90000


def test_merge_blocked_without_approvals():
    m = TemplateMarketplace()
    pr = m.propose(_good_spec(name="fraud"), author="bob")
    with pytest.raises(TemplateSpecError):
        m.merge(pr.pr_id, min_approvers=1)


def test_merge_blocked_with_invalid_spec():
    m = TemplateMarketplace()
    bad = _good_spec(name="ok2")
    bad["tdd_enforcement"] = "nope"
    pr = m.propose(bad, author="carol")
    # a spec with open problems cannot be approved
    with pytest.raises(TemplateSpecError):
        m.approve(pr.pr_id, "rev")
    # ...and therefore cannot be merged
    with pytest.raises(TemplateSpecError):
        m.merge(pr.pr_id)


def test_render_pr_payload():
    out = render_pr(_good_spec(), author="alice")
    assert out["filename"] == "charter/templates/logistics.json"
    assert "logistics" in out["title"]
    assert "```json" in out["body"]
    json.loads(out["json"])  # valid JSON

