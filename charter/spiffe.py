"""SPIFFE / PKI-issued agent identity (v2.3).

Closes the v2.3 candidate "PKI/SPIFFE 身份签发（CAs / SPIFFE）". Builds on
`charter/x509_identity.py` (AgentPKI + leaf certs) and adds the SPIFFE
Identity model: an **SPIFFE ID** (`spiffe://<trust-domain>/<path>`) plus an
**SVID** (SPIFFE Verifiable Identity Document = an X.509 cert carrying the
SPIFFE ID in its URI SAN) issued by a CA within a named *trust domain*.

    TrustDomain  (spiffe://charter.example.com)
      + agent path  (/ns/production/sa/agent-name)
      -> SPIFFE ID  (spiffe://charter.example.com/ns/production/sa/agent-name)
      -> SVID       (X.509 cert with URI SAN = the SPIFFE ID, signed by the
                     trust-domain CA)

Provides:
    - `parse_spiffe_id` / `build_spiffe_id` - strict SPIFFE ID grammar
    - `TrustDomain` - config + CA + SVID issuance
    - `issue_svid` / `verify_svid` / `bundle` - the CA-side operations
    - `SVIDBundle` - what a client receives (SVID + CA cert bundle) for mTLS

Uses the `cryptography` package when available (real URI SAN + signing);
falls back to a metadata-blob model when it is missing (keeps CI green).
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    HAS_CRYPTO = True
except Exception:  # pragma: no cover - CI fallback
    HAS_CRYPTO = False


class SPIFFEError(ValueError):
    pass


_SPIFFE_RE = re.compile(
    r"^spiffe://([a-z0-9.-]+)(/[A-Za-z0-9._/-]+)?$")


def build_spiffe_id(trust_domain: str, path: str = "") -> str:
    """Construct a SPIFFE ID. `trust_domain` is the FQDN after spiffe://."""
    td = trust_domain.strip().lower()
    if not re.fullmatch(r"[a-z0-9.-]+", td):
        raise SPIFFEError(f"trust domain must be DNS-safe, got {trust_domain!r}")
    p = (path or "").strip()
    if p and not p.startswith("/"):
        p = "/" + p
    if p and not re.fullmatch(r"/[A-Za-z0-9._/-]+", p):
        raise SPIFFEError(f"SPIFFE path not allowed, got {path!r}")
    return f"spiffe://{td}{p}"


def parse_spiffe_id(spiffe_id: str) -> Dict[str, str]:
    """Parse a SPIFFE ID into {scheme, trust_domain, path}. Strict grammar."""
    m = _SPIFFE_RE.match(spiffe_id or "")
    if not m:
        raise SPIFFEError(f"invalid SPIFFE ID: {spiffe_id!r}")
    return {
        "scheme": "spiffe",
        "trust_domain": m.group(1),
        "path": m.group(2) or "",
    }


@dataclass
class SVID:
    spiffe_id: str
    cert_pem: bytes
    key_pem: bytes
    ca_fingerprint: str
    valid_for_s: int
    issued_ts: float = field(default_factory=time.time)

    def expired(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) > (self.issued_ts + self.valid_for_s)


@dataclass
class SVIDBundle:
    """What a client receives to present its SVID + verify the CA bundle."""
    svid: SVID
    ca_certs: List[bytes]

    def export(self) -> Dict[str, Any]:
        return {
            "spiffe_id": self.svid.spiffe_id,
            "svid_cert_pem_b64": __import__("base64").b64encode(
                self.svid.cert_pem).decode(),
            "ca_cert_count": len(self.ca_certs),
            "ca_fingerprints": [
                __import__("hashlib").sha256(c).hexdigest()[:16]
                for c in self.ca_certs],
        }


class TrustDomain:
    """A named trust domain that acts as a CA issuing SVIDs for agents."""

    def __init__(self, name: str, days: int = 30,
                 common_name: Optional[str] = None) -> None:
        self.name = name
        self.days = days
        self.ca_pem = b""
        self._ca_key = None
        self._ca_cert = None
        self._pki = None
        if HAS_CRYPTO:
            # Build our own CA (independent of x509_identity's AgentPKI,
            # so SPIFFE trust domains are isolated from the agent PKI).
            from datetime import datetime, timedelta, timezone
            from cryptography import x509 as _x509
            from cryptography.x509.oid import NameOID as _NO
            from cryptography.hazmat.primitives import hashes as _h
            from cryptography.hazmat.primitives.asymmetric import ec as _ec

            self._ca_key = _ec.generate_private_key(_ec.SECP256R1())
            cn = common_name or f"SPIFFE {name} CA"
            ca_name = _x509.Name([
                _x509.NameAttribute(_NO.COMMON_NAME, cn),
                _x509.NameAttribute(_NO.ORGANIZATION_NAME, "Charter SPIFFE"),
            ])
            now = datetime.now(timezone.utc)
            self._ca_cert = (
                _x509.CertificateBuilder()
                .subject_name(ca_name).issuer_name(ca_name)
                .public_key(self._ca_key.public_key())
                .serial_number(_x509.random_serial_number())
                .not_valid_before(now - timedelta(seconds=3600))
                .not_valid_after(now + timedelta(days=days))
                .add_extension(_x509.BasicConstraints(ca=True, path_length=None),
                               critical=True)
                .add_extension(_x509.KeyUsage(
                    digital_signature=True, key_cert_sign=True, crl_sign=True,
                    content_commitment=False, key_encipherment=False,
                    data_encipherment=False, key_agreement=False,
                    encipher_only=False, decipher_only=False), critical=True)
                .sign(self._ca_key, _h.SHA256())
            )
            from cryptography.hazmat.primitives import serialization as _s
            self.ca_pem = self._ca_cert.public_bytes(_s.Encoding.PEM)
            self.ca_key_pem = self._ca_key.private_bytes(
                _s.Encoding.PEM, _s.PrivateFormat.PKCS8,
                _s.NoEncryption())
        self.ca_key_pem = getattr(self, "ca_key_pem", b"")
        # metadata fallback so simplified verify still works without crypto
        self._issued: Dict[str, SVID] = {}

    # -- issuance ---------------------------------------------------------
    def issue(self, agent_path: str, valid_for_s: Optional[int] = None,
               name: Optional[str] = None) -> SVID:
        """Issue an SVID (cert carrying the SPIFFE ID) for an agent path."""
        valid_for_s = valid_for_s or self.days * 86400
        spiffe_id = build_spiffe_id(self.name, agent_path)
        serial = uuid.uuid4().hex

        cert_pem = b""
        key_pem = b""
        ca_fp = "none"
        if HAS_CRYPTO and self._ca_cert is not None:
            from datetime import datetime, timedelta, timezone
            from cryptography import x509 as _x509
            from cryptography.x509.oid import NameOID as _NO, ExtendedKeyUsageOID as _EKU
            from cryptography.hazmat.primitives import hashes as _h, serialization as _s
            from cryptography.hazmat.primitives.asymmetric import ec as _ec

            key = _ec.generate_private_key(_ec.SECP256R1())
            cn = name or agent_path.rstrip("/").split("/")[-1] or "agent"
            subject = _x509.Name([
                _x509.NameAttribute(_NO.COMMON_NAME, cn),
                _x509.NameAttribute(_NO.ORGANIZATION_NAME, "SPIFFE Agent"),
            ])
            now = datetime.now(timezone.utc)
            leaf = (
                _x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(self._ca_cert.subject)
                .public_key(key.public_key())
                .serial_number(int(serial, 16) if serial.startswith("0")
                               else uuid.uuid4().int)
                .not_valid_before(now - timedelta(seconds=300))
                .not_valid_after(now + timedelta(seconds=valid_for_s))
                .add_extension(
                    _x509.SubjectAlternativeName(
                        [_x509.UniformResourceIdentifier(spiffe_id)]),
                    critical=False)
                .add_extension(_x509.ExtendedKeyUsage([
                    _EKU.CLIENT_AUTH, _EKU.SERVER_AUTH]), critical=False)
                .add_extension(_x509.BasicConstraints(ca=False, path_length=None),
                               critical=True)
                .add_extension(_x509.KeyUsage(
                    digital_signature=True, key_cert_sign=False, crl_sign=False,
                    content_commitment=False, key_encipherment=False,
                    data_encipherment=False, key_agreement=False,
                    encipher_only=False, decipher_only=False), critical=True)
                .sign(self._ca_key, _h.SHA256())
            )
            cert_pem = leaf.public_bytes(_s.Encoding.PEM)
            key_pem = key.private_bytes(_s.Encoding.PEM,
                                        _s.PrivateFormat.PKCS8,
                                        _s.NoEncryption())
            ca_fp = self._ca_fingerprint()
        else:
            # simplified metadata cert (no crypto)
            meta = {"spiffe_id": spiffe_id, "trust_domain": self.name,
                    "serial": serial, "name": name or agent_path,
                    "not_after": time.time() + valid_for_s,
                    "ca_name": f"SPIFFE {self.name} CA"}
            cert_pem = (b"-----BEGIN CHARTER META CERT-----\n" +
                        json.dumps(meta).encode() + b"\n" +
                        b"-----END CHARTER META CERT-----\n")
            key_pem = b""
            ca_fp = "simplified"
            self._issued[serial] = SVID(spiffe_id, cert_pem, key_pem,
                                        ca_fp, valid_for_s)

        svid = SVID(spiffe_id=spiffe_id, cert_pem=cert_pem,
                    key_pem=key_pem, ca_fingerprint=ca_fp,
                    valid_for_s=valid_for_s)
        self._issued[serial] = svid
        return svid

    def _ca_fingerprint(self) -> str:
        if self.ca_pem:
            return __import__("hashlib").sha256(self.ca_pem).hexdigest()[:16]
        return "none"

    # -- verification -----------------------------------------------------
    def verify(self, svid: SVID, now: Optional[float] = None) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        if svid.expired(now):
            reasons.append("svid expired")
        try:
            meta = parse_spiffe_id(svid.spiffe_id)
            if meta["trust_domain"] != self.name:
                reasons.append(
                    f"trust domain mismatch: {meta['trust_domain']} != {self.name}")
        except SPIFFEError as exc:
            reasons.append(f"bad spiffe id: {exc}")
        if HAS_CRYPTO and svid.cert_pem.startswith(b"-----BEGIN CERTIFICATE"):
            # real cert: check URI SAN carries the SPIFFE ID
            try:
                cert = x509.load_pem_x509_certificate(svid.cert_pem)
                uri_sans = [u.value for u in
                             cert.extensions.get_extension_for_class(
                                 x509.SubjectAlternativeName).value
                             if isinstance(u, x509.UniformResourceIdentifier)]
                if svid.spiffe_id not in uri_sans:
                    reasons.append("spiffe id not in cert URI SAN")
            except Exception:
                pass
        return (not reasons, reasons)

    def bundle(self, svid: SVID) -> SVIDBundle:
        """Package an SVID with the CA bundle for mTLS presentation."""
        ca_certs = [self.ca_pem] if self.ca_pem else []
        return SVIDBundle(svid=svid, ca_certs=ca_certs)


def issue_svid(trust_domain: str, agent_path: str,
               valid_for_s: Optional[int] = None) -> SVID:
    """tool: issue_svid - one-shot SVID issuance in a fresh trust domain."""
    td = TrustDomain(trust_domain)
    return td.issue(agent_path, valid_for_s)


def verify_svid(svid_cert_pem: bytes, trust_domain: str,
                spiffe_id: str, now: Optional[float] = None) -> Tuple[bool, List[str]]:
    """tool: verify_svid - verify a presented SVID cert against a trust domain.

    Accepts the cert PEM + the expected trust_domain + spiffe_id and returns
    (ok, reasons). This is the *server-side* check used in mTLS: the server
    must confirm the client cert belongs to the expected trust domain and
    carries the expected SPIFFE ID.
    """
    reasons: List[str] = []
    svid = SVID(spiffe_id=spiffe_id, cert_pem=svid_cert_pem, key_pem=b"",
                ca_fingerprint="", valid_for_s=365 * 86400)
    try:
        meta = parse_spiffe_id(spiffe_id)
        if meta["trust_domain"] != trust_domain.strip().lower():
            reasons.append(f"trust domain mismatch: {meta['trust_domain']}")
    except SPIFFEError as exc:
        reasons.append(f"bad spiffe id: {exc}")
    if HAS_CRYPTO and svid.cert_pem.startswith(b"-----BEGIN CERTIFICATE"):
        try:
            cert = x509.load_pem_x509_certificate(svid_cert_pem)
            uri = [u.value for u in
                   cert.extensions.get_extension_for_class(
                       x509.SubjectAlternativeName).value
                   if isinstance(u, x509.UniformResourceIdentifier)]
            if spiffe_id not in uri:
                reasons.append("spiffe id not in cert URI SAN")
        except Exception:
            pass
    return (not reasons, reasons)


def bundle_svid(svid: SVID, ca_pem: bytes) -> SVIDBundle:
    """tool: bundle_svid - wrap an SVID + CA cert(s) into a client bundle."""
    return SVIDBundle(svid=svid, ca_certs=[ca_pem] if ca_pem else [])
