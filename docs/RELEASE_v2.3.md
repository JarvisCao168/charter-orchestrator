# v2.3.0 — Production Linkage Hardening

Charter Orchestrator v2.3.0 hardens the v2.2 production linkages with four
new modules: real mTLS, GitHub-PR automation for the template marketplace,
a caching production embedding endpoint, and SPIFFE/PKI identity issuance.

## New modules

### 1. Real mTLS — `charter/mtls.py`
Server-side certificate verification:
- `TrustAnchor` (CA PEM + revocation set) with `verify_chain` checking
  issuer match, EKU clientAuth, validity window, revocation, and CA
  signature (via `cryptography` when available).
- `verify_server_cert` for the reverse direction (SAN/CN name check).
- `mtls_check(...)` — one-shot both-directions verification returning an
  `MTLSResult`; `bool(result)` is True only when both pass.
- Simplified PEM-metadata fallback when `cryptography` is missing (keeps CI
  green offline).

### 2. Template marketplace → GitHub PR — `charter/github_pr.py`
`open_template_pr(spec, repo=..., token=...)`:
- validates the candidate template (reuses `template_pr.validate_template`),
- prepares the branch + commit + PR body,
- live-opens a (draft) PR when a token + repo are available,
- **offline-safe**: no token / no network → returns a `PRResult(draft=True)`
  with the fully-prepared payload, no exception.

### 3. Production embedding endpoint + cache — `charter/embed_cache.py`
- `EmbedCache`: two-level LRU + optional SQLite disk store keyed by
  `(backend, model, dim, sha256(text))`.
- `CachedEmbedder`: wraps any underlying embedder; cache-miss calls the
  underlying, then stores.
- `production_embedder(...)`: auto-detects AGNES/OPENAI key, else falls back
  to the offline hashing embedder; returns a `CachedEmbedder`.
- `embed_with_cache(...)`: one-shot embed + cache-state report.

### 4. SPIFFE / PKI-issued identity — `charter/spiffe.py`
- `build_spiffe_id` / `parse_spiffe_id`: strict `spiffe://<td>/<path>` grammar.
- `TrustDomain`: per-trust-domain CA (independent of the agent PKI); issues
  **SVIDs** (X.509 certs carrying the SPIFFE ID in a URI SAN).
- `verify_svid` / `bundle_svid`: server-side verification + client bundle
  for mTLS presentation.
- Fallback metadata-cert model when `cryptography` is absent.

## Tests
+18 new tests in `tests/test_v2_3.py` (56 → 74 total, all green on
Python 3.9 / 3.11 / 3.12 CI). They assert the offline-safe contracts
(degradation / draft-fallback / cache-hit / SPIFFE grammar) rather than
live network calls.

## Install
```
pip install charter-orchestrator          # stdlib-only core
pip install "charter-orchestrator[crypto]"# + X.509/mTLS/SPIFFE identity
pip install "charter-orchestrator[llm]"   # + HTTP embedders / online judge
```

## Roadmap (v2.4)
- Multi-model judge consensus scoring
- LLM summary compression for cross-session memory
- Trace SLO → real alerting (Alertmanager / PagerDuty)
- SPIFFE → real SPIRE Server (gRPC)
- Template PR auto-CI + community scoring
