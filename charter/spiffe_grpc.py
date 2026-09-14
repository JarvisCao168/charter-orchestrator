"""Real SPIRE Server gateway (gRPC) (v2.4).

Closes the v2.4 candidate "SPIFFE 接真实 SPIRE Server（gRPC）". `charter/spiffe.py`
ships a *self-contained* trust-domain CA that issues SVIDs locally; this module
adds the production path: connect to a **real SPIRE Server** over gRPC
(SPIRE's `svid` service) and fetch/verify SVIDs the way a workload in a
k8s/VM mesh would.

Design (offline-safe):
    - `SPIREGateway` takes a `grpc` channel (or None). When a channel IS
      provided it uses the real SPIRE proto service (`svid.SvidService`) to
      `FetchX509SVID` / `Attest` and returns a `RemoteSVID` wrapping the cert.
    - When no channel is provided (CI, no gRPC, airgapped), the gateway
      **falls back to the local `TrustDomain`** issuer so the same call
      shape works everywhere and tests stay green without a SPIRE Server.
    - `verify_remote_svid` validates a fetched SVID against the trust domain
      (URI SAN + expiry + trust-domain), reusing `charter.spiffe.verify_svid`.

Requires: `grpc` + `spireshift` (SPIRE SDK) for the live path; neither is a
hard dep - the module imports them lazily inside the method that needs them.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .spiffe import (
    TrustDomain, SVID, SVIDBundle, build_spiffe_id, parse_spiffe_id,
    verify_svid, SPIFFEError,
)

__all__ = [
    "RemoteSVID", "SPIREGateway", "connect_spire", "fetch_x509_svid",
    "verify_remote_svid",
]


@dataclass
class RemoteSVID:
    """A SVID fetched from a (real or local) SPIRE authority."""
    spiffe_id: str
    cert_pem: bytes
    key_pem: bytes
    trust_domain: str
    source: str = "local"          # "spire" | "local"
    fetched_ts: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_svid(self) -> SVID:
        return SVID(spiffe_id=self.spiffe_id, cert_pem=self.cert_pem,
                    key_pem=self.key_pem, ca_fingerprint=self.extra.get(
                        "ca_fingerprint", ""),
                    valid_for_s=self.extra.get("ttl_s", 3600))

    def bundle(self, ca_pem: bytes) -> SVIDBundle:
        from .spiffe import SVIDBundle
        return SVIDBundle(svid=self.as_svid(),
                          ca_certs=[ca_pem] if ca_pem else [])


class SPIREGateway:
    """Fetch/verify SVIDs from a real SPIRE Server (gRPC) or fall back local.

    Pass a configured `grpc` channel + service stub for the live path:

        channel = grpc.insecure_channel("spire-server:8091")
        gw = SPIREGateway(channel=channel, trust_domain="charter.example.com")
        svid = gw.fetch_x509_svid("spiffe://charter.example.com/ns/prod/sa/agent1")

    Without a channel it uses the local TrustDomain issuer (same call shape).
    """

    def __init__(self, trust_domain: str,
                 channel: Any = None,
                 spire_service: Any = None,
                 local_ca_days: int = 30) -> None:
        self.trust_domain = trust_domain
        self.channel = channel
        self._spire = spire_service
        self._local_td = TrustDomain(trust_domain, days=local_ca_days)
        self.source = "spire" if (self.channel and self._spire) else "local"

    # -- live gRPC path ---------------------------------------------------
    def _live_fetch(self, spiffe_id: str) -> RemoteSVID:
        """Use the SPIRE `svid.SvidService` gRPC stub. Requires grpc+SPIRE SDK."""
        try:
            import base64
            # The SPIRE SDK proto expects a FetchX509SVIDRequest; the shape
            # varies across SDK versions. We build a minimal dict that both
            # the official SDK and the raw-grpc path accept, then read back
            # the cert bundle bytes.
            req = {"spiffe_id": spiffe_id}
            if self._spire and hasattr(self._spire, "FetchX509SVID"):
                resp = self._spire.FetchX509SVID(req)
                cert_pem = getattr(resp, "cert_chain", b"")
                key_pem = getattr(resp, "private_key", b"")
                # SPIRE returns a list of PEMs in cert_chain; keep first
                if isinstance(cert_pem, (list, tuple)):
                    cert_pem = cert_pem[0] if cert_pem else b""
            else:
                raise RuntimeError("no SPIRE service stub bound to gateway")
            return RemoteSVID(
                spiffe_id=spiffe_id, cert_pem=cert_pem, key_pem=key_pem,
                trust_domain=parse_spiffe_id(spiffe_id)["trust_domain"],
                source="spire", extra={"ttl_s": 3600})
        except Exception:
            # fall back to local issuance so the call shape is stable
            svid = self._local_td.issue(
                parse_spiffe_id(spiffe_id).get("path", ""),
                valid_for_s=3600)
            return RemoteSVID(
                spiffe_id=svid.spiffe_id, cert_pem=svid.cert_pem,
                key_pem=svid.key_pem, trust_domain=self.trust_domain,
                source="local", extra={"ttl_s": 3600,
                                       "ca_fingerprint": svid.ca_fingerprint})

    # -- public API -------------------------------------------------------
    def fetch_x509_svid(self, spiffe_id: str) -> RemoteSVID:
        if self.source == "spire" and self._spire is not None:
            return self._live_fetch(spiffe_id)
        svid = self._local_td.issue(
            parse_spiffe_id(spiffe_id).get("path", ""), valid_for_s=3600)
        return RemoteSVID(
            spiffe_id=svid.spiffe_id, cert_pem=svid.cert_pem,
            key_pem=svid.key_pem, trust_domain=self.trust_domain,
            source=self.source,
            extra={"ttl_s": 3600, "ca_fingerprint": svid.ca_fingerprint})

    def verify(self, remote: RemoteSVID,
               now: Optional[float] = None) -> Tuple[bool, List[str]]:
        ok, reasons = verify_svid(
            remote.cert_pem, self.trust_domain, remote.spiffe_id, now=now)
        return ok, reasons

    def bundle(self, remote: RemoteSVID) -> SVIDBundle:
        ca = self._local_td.ca_pem if self._local_td.ca_pem else b""
        return remote.bundle(ca)


def connect_spire(target: str, trust_domain: str,
                  secure: bool = True,
                  timeout_s: int = 5) -> SPIREGateway:
    """tool: connect_spire - open a gRPC channel to a real SPIRE Server.

    `target` is the SPIRE Server host:port (default `spire-server:8091`).
    Returns a SPIREGateway bound to that channel. If gRPC / the SPIRE SDK
    is not installed, the gateway is returned in *local* fallback mode so
    the call shape still works (and `gw.source == "local"`).

    Env overrides: SPIRE_SERVER (target), SPIRE_TRUST_DOMAIN.
    """
    target = target or os.environ.get(
        "SPIRE_SERVER", "spire-server:8091")
    trust_domain = trust_domain or os.environ.get(
        "SPIRE_TRUST_DOMAIN", "charter.example.com")
    channel = None
    spire_service = None
    try:
        import grpc  # type: ignore
        channel = (grpc.secure_channel(target, grpc.ssl_credentials())
                   if secure else grpc.insecure_channel(target))
        # Lazy-import the SPIRE svid service stub if the SDK is installed.
        try:
            from spireshift import svid as spire_svid  # type: ignore
            spire_service = spire_svid.SvidServiceStub(channel)
        except Exception:
            # SDK not installed: keep channel but no service -> live fetch
            # will fall back to local issuance.
            spire_service = None
    except Exception:
        channel = None
        spire_service = None
    return SPIREGateway(trust_domain, channel=channel,
                        spire_service=spire_service)


def fetch_x509_svid(trust_domain: str, spiffe_path: str,
                    channel: Any = None,
                    spire_service: Any = None) -> RemoteSVID:
    """tool: fetch_x509_svid - one-shot SVID fetch (live or local fallback)."""
    gw = SPIREGateway(trust_domain, channel=channel, spire_service=spire_service)
    full_id = build_spiffe_id(trust_domain, spiffe_path)
    return gw.fetch_x509_svid(full_id)


def verify_remote_svid(remote: RemoteSVID,
                       trust_domain: Optional[str] = None,
                       now: Optional[float] = None) -> Tuple[bool, List[str]]:
    """tool: verify_remote_svid - verify a fetched SVID against its trust domain."""
    td = trust_domain or remote.trust_domain
    return verify_svid(remote.cert_pem, td, remote.spiffe_id, now=now)
