"""Agent cryptographic identity & signed tool calls (v2.0).

Closes the Red Hat "7 missing production capabilities" #1 gap: every agent
gets a signed identity; every tool call is HMAC-signed with a nonce + expiry
so it can be verified, replay-checked, and attributed. Uses stdlib only
(hashlib HMAC-SHA256) so it runs in CI with no `cryptography` dependency.

Model (X.509-inspired, simplified to a registry):
    AgentIdentity  = (agent_id, public_key_id, capabilities, issued_ts, ttl)
    SignedCall     = HMAC(key, agent_id | tool | nonce | ts | payload_digest)
The "key" is a per-agent secret derived from the registry root key + agent_id
(KDF). In production, swap the KDF for X.509/mTLS (see SKILL.md v2.0 roadmap).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _kdf(root_key: str, agent_id: str) -> bytes:
    """Derive a per-agent signing key from the registry root key + agent id."""
    return hashlib.shake_256(
        f"charter:{root_key}:{agent_id}".encode("utf-8")).digest(32)


@dataclass
class AgentIdentity:
    agent_id: str
    key_id: str
    capabilities: List[str]
    issued_ts: float
    ttl_s: int = 3600

    def expired(self, now: Optional[float] = None) -> bool:
        return (now or time.time()) > (self.issued_ts + self.ttl_s)


class IdentityRegistry:
    """Issue + verify agent identities and signed tool calls."""

    def __init__(self, root_key: Optional[str] = None,
                 trust_on_first_use: bool = True) -> None:
        self.root_key = root_key or uuid.uuid4().hex
        self.trust_on_first_use = trust_on_first_use
        self._identities: Dict[str, AgentIdentity] = {}
        self._nonces: Dict[str, float] = {}   # nonce -> expiry ts (anti-replay)
        self._audit: List[Dict[str, Any]] = []

    # -- identity --
    def issue(self, agent_id: str, capabilities: List[str],
              ttl_s: int = 3600) -> AgentIdentity:
        ident = AgentIdentity(
            agent_id=agent_id,
            key_id=hashlib.sha256(_kdf(self.root_key, agent_id)).hexdigest()[:16],
            capabilities=list(capabilities),
            issued_ts=time.time(),
            ttl_s=ttl_s,
        )
        self._identities[agent_id] = ident
        self._audit.append({"event": "issue", "agent": agent_id,
                            "caps": capabilities, "ts": ident.issued_ts})
        return ident

    def get(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._identities.get(agent_id)

    # -- signed tool calls --
    def sign_call(self, agent_id: str, tool: str,
                  payload: Dict[str, Any],
                  nonce: Optional[str] = None,
                  ts: Optional[float] = None) -> Dict[str, str]:
        ident = self._identities.get(agent_id)
        if ident is None:
            raise PermissionError(f"unknown agent {agent_id!r}; call issue() first")
        if tool not in ident.capabilities:
            raise PermissionError(
                f"agent {agent_id} lacks capability {tool!r} "
                f"(has {ident.capabilities})")
        nonce = nonce or uuid.uuid4().hex
        ts = ts or time.time()
        payload_digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        msg = "|".join([agent_id, tool, nonce, f"{ts:.6f}", payload_digest])
        key = _kdf(self.root_key, agent_id)
        sig = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
        return {
            "agent_id": agent_id, "tool": tool, "nonce": nonce,
            "ts": f"{ts:.6f}", "payload_digest": payload_digest,
            "signature": sig,
        }

    def verify_call(self, call: Dict[str, str],
                    payload: Optional[Dict[str, Any]] = None,
                    max_age_s: float = 600.0) -> Dict[str, Any]:
        agent_id = call["agent_id"]
        ident = self._identities.get(agent_id)
        now = time.time()
        problems: List[str] = []

        if ident is None:
            if not self.trust_on_first_use:
                return {"ok": False, "reasons": ["unknown agent"]}
            # TOFU: register implicitly with no caps -> will fail capability check
            self.issue(agent_id, [])
        if ident.expired(now):
            problems.append("identity expired")
        # recompute digest if payload provided
        pd = call.get("payload_digest", "")
        if payload is not None:
            pd = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()
            if pd != call.get("payload_digest", pd):
                problems.append("payload digest mismatch")
        msg = "|".join([agent_id, call.get("tool", ""), call.get("nonce", ""),
                        call.get("ts", ""), pd])
        key = _kdf(self.root_key, agent_id)
        expect = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, call.get("signature", "")):
            problems.append("signature invalid")
        # capability
        if call.get("tool") and call["tool"] not in ident.capabilities:
            problems.append(f"capability missing: {call['tool']}")
        # anti-replay
        nonce = call.get("nonce", "")
        if nonce in self._nonces:
            problems.append("replayed nonce")
        else:
            self._nonces[nonce] = now + max_age_s
        ts = float(call.get("ts", "0") or 0)
        if now - ts > max_age_s:
            problems.append("call too old")
        ok = not problems
        self._audit.append({"event": "verify", "agent": agent_id,
                            "ok": ok, "problems": problems, "ts": now})
        return {"ok": ok, "problems": problems, "agent": agent_id,
                "capability_ok": call.get("tool") in ident.capabilities}

    # -- audit + housekeeping --
    def audit_log(self, limit: int = 200) -> List[Dict[str, Any]]:
        return self._audit[-limit:]

    def purge_nonces(self, now: Optional[float] = None) -> int:
        now = now or time.time()
        dead = [n for n, exp in self._nonces.items() if exp < now]
        for n in dead:
            del self._nonces[n]
        return len(dead)


# ---------------------------------------------------------------------------
# Default registry + convenience tools
# ---------------------------------------------------------------------------
_DEFAULT = IdentityRegistry()


def issue_agent(agent_id: str, capabilities: List[str],
                ttl_s: int = 3600,
                registry: Optional[IdentityRegistry] = None) -> AgentIdentity:
    return (registry or _DEFAULT).issue(agent_id, capabilities, ttl_s)


def sign_tool_call(agent_id: str, tool: str,
                   payload: Dict[str, Any],
                   registry: Optional[IdentityRegistry] = None) -> Dict[str, str]:
    return (registry or _DEFAULT).sign_call(agent_id, tool, payload)


def verify_tool_call(call: Dict[str, str],
                     payload: Optional[Dict[str, Any]] = None,
                     registry: Optional[IdentityRegistry] = None) -> Dict[str, Any]:
    return (registry or _DEFAULT).verify_call(call, payload)
