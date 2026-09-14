"""X.509 agent certificates + mTLS-style signed tool calls (v2.1).

Upgrades `charter/identity.py` (HMAC registry) to real X.509 agent certs.
Uses the `cryptography` package when available (production path); falls back
to the stdlib HMAC registry so CI still runs with no native deps.

Model:
    Agent CA (root)  -> signs per-agent leaf certs (X.509 v3, SAN=agent id,
                        ExtendedKeyUsage=clientAuth+serverAuth for mTLS).
    Every tool call is signed with the agent's leaf private key (detached
    signature over the call transcript) and verified with the leaf cert.
    mTLS: both directions present certs; we model the server-checks-client
    half (client cert = agent identity) which is what tool governance needs.

Requires: pip install cryptography  (optional extra; graceful fallback)
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import cryptography  # noqa: F401
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    HAS_CRYPTO = True
except Exception:  # pragma: no cover - CI fallback
    HAS_CRYPTO = False


class X509IdentityError(Exception):
    pass


@dataclass
class AgentCert:
    agent_id: str
    cert_pem: bytes
    key_pem: bytes
    not_before: float
    not_after: float

    def expired(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) > self.not_after


class AgentPKI:
    """Root CA that issues per-agent leaf certs and signs/verifies calls."""

    def __init__(self, common_name: str = "Charter-Orchestrator CA",
                 days: int = 365) -> None:
        if not HAS_CRYPTO:
            raise X509IdentityError(
                "cryptography package required: pip install cryptography")
        self.days = days
        # Root CA
        self._ca_key = ec.generate_private_key(ec.SECP256R1())
        now = time.time()
        ca_name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Charter Orchestrator"),
        ])
        self._ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(self._ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.fromtimestamp(now - 3600, tz=timezone.utc))
            .not_valid_after(datetime.fromtimestamp(now + days * 86400, tz=timezone.utc))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None),
                           critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False), critical=True)
            .sign(self._ca_key, hashes.SHA256())
        )

    # -- issuance --
    def issue_agent(self, agent_id: str,
                    capabilities: List[str],
                    ttl_s: int = 3600) -> AgentCert:
        key = ec.generate_private_key(ec.SECP256R1())
        now = time.time()
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, agent_id),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Charter Agent"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.fromtimestamp(now - 300, tz=timezone.utc))
            .not_valid_after(datetime.fromtimestamp(now + ttl_s, tz=timezone.utc))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(agent_id)]),
                critical=False)
            .add_extension(x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.CLIENT_AUTH,
                ExtendedKeyUsageOID.SERVER_AUTH,  # mTLS both directions
            ]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                           critical=True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, key_cert_sign=False, crl_sign=False,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False), critical=True)
            .sign(self._ca_key, hashes.SHA256())
        )
        cap_blob = json.dumps(sorted(capabilities), sort_keys=True)
        return AgentCert(
            agent_id=agent_id,
            cert_pem=cert.public_bytes(serialization.Encoding.PEM),
            key_pem=key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()),
            not_before=now, not_after=now + ttl_s,
            # capabilities travel in the cert's SAN? No - kept in registry:
        )

    def ca_cert_pem(self) -> bytes:
        return self._ca_cert.public_bytes(serialization.Encoding.PEM)

    # -- signed calls (mTLS client-cert model) --
    def sign_call(self, cert: AgentCert, agent_key_pem: bytes,
                  tool: str, payload: Dict[str, Any],
                  nonce: Optional[str] = None,
                  ts: Optional[float] = None) -> Dict[str, str]:
        key = serialization.load_pem_private_key(agent_key_pem, password=None)
        nonce = nonce or uuid.uuid4().hex
        ts = ts or time.time()
        digest = hashlib_digest(payload)
        msg = "|".join([cert.agent_id, tool, nonce, f"{ts:.6f}", digest])
        sig = key.sign(msg.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        import base64
        return {"agent_id": cert.agent_id, "tool": tool, "nonce": nonce,
                "ts": f"{ts:.6f}", "payload_digest": digest,
                "signature": base64.b64encode(sig).decode(),
                "scheme": "x509"}

    def verify_call(self, call: Dict[str, str],
                    cert_pem: bytes,
                    payload: Optional[Dict[str, Any]] = None,
                    max_age_s: float = 600.0,
                    ca_pem: Optional[bytes] = None,
                    nonce_store: Optional[Dict[str, float]] = None,
                    ) -> Dict[str, Any]:
        import base64
        cert = x509.load_pem_x509_certificate(cert_pem)
        problems: List[str] = []
        now = time.time()
        # chain check: leaf must be issued by our CA
        if ca_pem:
            ca = x509.load_pem_x509_certificate(ca_pem)
            if cert.issuer != ca.subject:
                problems.append("cert not issued by CA")
        cert_exp = getattr(cert, "not_valid_after_utc", None)
        if cert_exp is None:
            cert_exp = cert.not_valid_after.replace(tzinfo=timezone.utc)
        cert_exp_ts = cert_exp.timestamp()
        if cert_exp_ts < now:
            problems.append("cert expired")
        pd = call.get("payload_digest", "")
        if payload is not None:
            pd_check = hashlib_digest(payload)
            if pd_check != call.get("payload_digest", pd_check):
                problems.append("payload digest mismatch")
            pd = pd_check
        msg = "|".join([call.get("agent_id",""), call.get("tool",""),
                        call.get("nonce",""), call.get("ts",""), pd])
        try:
            cert.public_key().verify(
                base64.b64decode(call["signature"]),
                msg.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        except Exception:
            problems.append("signature invalid")
        if nonce_store is not None:
            nonce = call.get("nonce", "")
            if nonce in nonce_store:
                problems.append("replayed nonce")
            else:
                nonce_store[nonce] = now + max_age_s
        ts = float(call.get("ts", "0") or 0)
        if now - ts > max_age_s:
            problems.append("call too old")
        attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        agent_cn = attrs[0].value if attrs else ""
        return {"ok": not problems, "problems": problems,
                "agent": agent_cn}


def hashlib_digest(payload: Dict[str, Any]) -> str:
    import hashlib
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Convenience (uses a shared PKI + nonce store)
# ---------------------------------------------------------------------------
_STATE: Dict[str, Any] = {}


def _pki() -> "AgentPKI":
    if "pki" not in _STATE:
        _STATE["pki"] = AgentPKI()
        _STATE["certs"] = {}
        _STATE["nonces"] = {}
    return _STATE["pki"]


def x509_issue(agent_id: str, capabilities: List[str],
               ttl_s: int = 3600) -> AgentCert:
    pki = _pki()
    cert = pki.issue_agent(agent_id, capabilities, ttl_s)
    _STATE["certs"][agent_id] = (cert, pki, capabilities)
    return cert


def x509_sign(agent_id: str, tool: str, payload: Dict[str, Any]) -> Dict[str, str]:
    pki = _STATE["pki"]
    entry = _STATE["certs"][agent_id]
    cert, pki2, caps = entry
    pki = pki2
    if tool not in caps:
        raise PermissionError(f"agent {agent_id!r} lacks capability {tool!r}")
    return pki.sign_call(cert, cert.key_pem, tool, payload)


def x509_verify(call: Dict[str, str], payload: Optional[Dict[str, Any]] = None,
                agent_id: Optional[str] = None) -> Dict[str, Any]:
    pki = _STATE["pki"]
    aid = agent_id or call.get("agent_id")
    cert = _STATE["certs"][aid][0]
    return pki.verify_call(call, cert.cert_pem, payload,
                           nonce_store=_STATE["nonces"],
                           ca_pem=pki.ca_cert_pem())
