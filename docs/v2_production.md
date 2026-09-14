# v2.1 Hardened Production / v2.1 生产加固

Four upgrades take the v2.0 layers from "runs" to "production-grade".

## 1. X.509 Agent Certificates + mTLS (replaces HMAC) / `charter/x509_identity.py`

Real X.509 agent certs (EC P-256) issued by a built-in root CA; every tool
call is ECDSA-signed and verified. Anti-replay, capability-bound, and chain-
validated. Optional extra: `pip install charter-orchestrator[crypto]`.

```python
from charter import x509_issue, x509_sign, x509_verify
cert = x509_issue("dev-1", ["execute_in_sandbox"])
call = x509_sign("dev-1", "execute_in_sandbox", {"cmd": "pytest"})
assert x509_verify(call, {"cmd": "pytest"})["ok"]
# replay / tamper / capability / expiry all rejected
```

Without `cryptography`, the stdlib HMAC path in `charter/identity.py` stays
available as the fallback, so CI is green with or without the extra.

## 2. Real Grafana Data Source Provisioning / `charter/grafana.py`

Goes beyond the v2.0 dashboard JSON: provisions a **Prometheus data source**,
a **Tempo** trace data source, a scrape config, and an OTLP exporter target,
all importable into a Grafana stack.

```python
from charter import live_metrics_demo
bundle = live_metrics_demo()
print(bundle["prometheus_ds"])   # -> /etc/grafana/provisioning/datasources
print(bundle["dashboard"])       # -> importable dashboard with traces panel
print(bundle["prometheus_scrape"])  # -> prometheus.yml scrape config
```

## 3. LLM Embedding Backends / `charter/llm_embed.py`

Swaps the offline hashing embedder for a *real* semantic model. Provider-
agnostic via the `Embedder` protocol; builtin `AgnesEmbedder` and
`OpenAIEmbedder` (OpenAI-compatible `/embeddings`, stdlib HTTP, no `requests`).

```python
from charter import VectorMemory, AgnesEmbedder
vm = VectorMemory(path="mem.sqlite", embed=AgnesEmbedder(model="agnes-embed"))
vm.remember("dev-1", "we chose SQLite as the cache layer")
vm.recall("dev-1", "cache storage decision")   # true semantic ranking
```

Pass any `(text, dim) -> [float]` as `embed=`; in CI with no key, the hashing
embedder remains the default so tests stay green offline.

## 4. Template Marketplace PR Flow / `charter/template_pr.py`

Community industry templates now go through a governance PR gate instead of a
bare file drop: schema-validate → review/approve → merge. `render_pr()` emits
the exact GitHub PR payload (title + checklist body + JSON) so a human or CI
can open it.

```python
from charter import TemplateMarketplace, render_pr
m = TemplateMarketplace()
pr = m.propose({...spec...}, author="alice")
m.approve(pr.pr_id, "reviewer-1")
m.merge(pr.pr_id)             # now loadable
print(render_pr(spec, "alice"))  # -> {repo, filename, title, body, json}
```

---
## Optional Extras / 可选依赖

```bash
pip install "charter-orchestrator[crypto]"   # X.509 identity
pip install "charter-orchestrator[llm]"      # requests for LLM embedders
```

Both are optional - the core + fallbacks run on stdlib alone.
