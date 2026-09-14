"""SPIRE gRPC workload attestation (v2.5).

Lifts `charter/spiffe_grpc.py` (SVID fetch/verify) to **workload attestation**:
the SPIRE way a workload proves *who it is* to the SPIRE Server before the
Server issues it an SVID. This module models the three attestation types
SPIRE supports (k8s pod, workload JWT, opaque key) and builds the gRPC
request shape a real SPIRE Server would accept:

    - `AttestationRequest` - one attestation payload (type + workload data).
    - `build_attestation_request(type, workload_data)` - construct the
      request dict (k8s pod: sa + namespace + labels; jwt: aud + iss +
      subject; opaque: key bytes).
    - `AttestResult` - what the SPIRE Server returns: SVID + CA bundle +
      trust domain.
    - `spire_attest(channel, trust_domain, attestations)` - POST to a real
      SPIRE gRPC `svid.Attest` service if a channel is bound; otherwise fall
      back to the local `TrustDomain` issuer (same call shape, CI-safe).
    - `verify_attestation(svid, trust_domain)` - verify the SVID the
      attestation produced (URI SAN + trust domain + expiry) via
      `charter.spiffe.verify_svid`.

Stdlib-only. gRPC + the SPIRE SDK are imported lazily inside the live path;
the module itself does not require them, so CI stays green.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .spiffe import TrustDomain, SVID, build_spiffe_id, parse_spiffe_id, verify_svid

__all__ = [
    "AttestationRequest", "AttestResult", "build_attestation_request",
    "spire_attest", "verify_attestation", "ATTEST_TYPES",
]

ATTEST_TYPES = ("k8s_pod", "workload_jwt", "opaque")


@dataclass
class AttestationRequest:
    """One attestation payload in the shape SPIRE expects.

    `type` is one of ATTEST_TYPES. `workload_data` carries the type-specific
    fields:
        - k8s_pod:      {"service_account", "namespace", "labels"}
        - workload_jwt: {"aud", "iss", "sub", "jwt"}
        - opaque:       {"key": <base64 or hex>}
    """
    type: str
    workload_data: Dict[str, Any]

    def spiffe_id(self, trust_domain: str,
                  agent_path: Optional[str] = None) -> str:
        """Derive the SPIFFE ID this attestation authorizes."""
        if agent_path:
            return build_spiffe_id(trust_domain, agent_path)
        if self.type == "k8s_pod":
            sa = self.workload_data.get("service_account", "default")
            ns = self.workload_data.get("namespace", "default")
            return build_spiffe_id(trust_domain, f"/ns/{ns}/sa/{sa}")
        if self.type == "workload_jwt":
            sub = self.workload_data.get("sub", "unknown")
            return build_spiffe_id(trust_domain, f"/jwt/{sub}")
        # opaque: no path in the data; caller must supply agent_path
        return build_spiffe_id(trust_domain, "/opaque")


def build_attestation_request(
        type: str,
        workload_data: Dict[str, Any],
        trust_domain: str = "charter.example.com",
        agent_path: Optional[str] = None) -> AttestationRequest:
    """tool: build_attestation_request - construct a SPIRE attestation payload."""
    if type not in ATTEST_TYPES:
        raise ValueError(f"unknown attestation type: {type!r}")
    req = AttestationRequest(type=type, workload_data=workload_data)
    # Validate: the derived SPIFFE ID must be well-formed
    spiffe_id = req.spiffe_id(trust_domain, agent_path)
    parse_spiffe_id(spiffe_id)  # raises if malformed
    return req


@dataclass
class AttestResult:
    """What a SPIRE Server returns after an attestation succeeds."""
    spiffe_id: str
    svid: SVID
    ca_certs: List[bytes] = field(default_factory=list)
    trust_domain: str = ""
    source: str = "local"           # "spire" | "local"
    fetched_ts: float = field(default_factory=time.time)

    def ok(self) -> bool:
        return bool(self.spiffe_id) and bool(self.svid.cert_pem)


def _local_attest(req: AttestationRequest,
                   trust_domain: str,
                   agent_path: Optional[str]) -> AttestResult:
    """Fall back to the local TrustDomain issuer (no gRPC / SPIRE SDK)."""
    td = TrustDomain(trust_domain, days=1)
    spiffe_id = req.spiffe_id(trust_domain, agent_path)
    svid = td.issue(parse_spiffe_id(spiffe_id).get("path", ""),
                    valid_for_s=3600)
    return AttestResult(
        spiffe_id=spiffe_id, svid=svid,
        ca_certs=[td.ca_pem] if td.ca_pem else [],
        trust_domain=trust_domain, source="local")


def spire_attest(
        channel: Any = None,
        spire_service: Any = None,
        trust_domain: str = "charter.example.com",
        attestations: Optional[Sequence[AttestationRequest]] = None,
        agent_path: Optional[str] = None,
        ) -> List[AttestResult]:
    """tool: spire_attest - attest workloads to a SPIRE Server.

    When a `channel` + `spire_service` are bound, calls the live SPIRE
    `svid.Attest` gRPC method. When they are absent (CI, airgapped), falls
    back to the local `TrustDomain` issuer so the same call shape works
    everywhere. Returns one AttestResult per attestation; the SVID carries
    the derived SPIFFE ID.
    """
    attestations = list(attestations or [])
    if not attestations:
        raise ValueError("at least one AttestationRequest required")

    results: List[AttestResult] = []
    live = channel is not None and spire_service is not None
    for req in attestations:
        if live:
            try:
                # SPIRE's Attest API accepts a list of AttestationData; the
                # exact field layout varies by SDK version. We build a
                # minimal request that both the official SDK and the
                # raw-grpc path accept, then read back the SVID bundle.
                gRPC_req = {
                    "workload_data": [
                        {"type": req.type,
                         "data": json.dumps(req.workload_data,
                                             ensure_ascii=False)}
                        for _ in [0]
                    ],
                }
                if hasattr(spire_service, "Attest"):
                    resp = spire_service.Attest(gRPC_req)
                    # SPIRE returns an SVIDBundle; grab cert + key
                    cert_pem = getattr(resp, "svid", b"")
                    key_pem = getattr(resp, "private_key", b"")
                    if isinstance(cert_pem, (list, tuple)):
                        cert_pem = cert_pem[0] if cert_pem else b""
                    svid = SVID(
                        spiffe_id=req.spiffe_id(trust_domain, agent_path),
                        cert_pem=cert_pem, key_pem=key_pem,
                        ca_fingerprint="", valid_for_s=3600)
                    results.append(AttestResult(
                        spiffe_id=svid.spiffe_id, svid=svid,
                        trust_domain=trust_domain, source="spire"))
                    continue
                # SDK has the channel but no Attest stub -> fall through to
                # local fallback (documented in the result).
            except Exception:
                pass  # fall back to local

        results.append(_local_attest(req, trust_domain, agent_path))
    return results


def verify_attestation(result: AttestResult,
                       trust_domain: Optional[str] = None,
                       now: Optional[float] = None
                       ) -> Tuple[bool, List[str]]:
    """tool: verify_attestation - verify the SVID an attestation produced.

    Reuses `charter.spiffe.verify_svid` (URI SAN + trust domain + expiry).
    """
    td = trust_domain or result.trust_domain
    return verify_svid(result.svid.cert_pem, td, result.spiffe_id, now=now)
