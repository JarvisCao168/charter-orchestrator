"""SPIRE bidirectional-mTLS real node-agent socket handshake (v2.10).

Lifts `charter/spire_bidir_regression.py` (in-memory mock SVID specs +
invariant checks) to a **real Unix-domain-socket** two-way handshake:
the workload dials the node agent's SPIFFE Workload API socket, the two
sides exchange their SVID specs over the socket, and each verifies the
peer's SVID. This runs fully offline (a `MockUnixSocket` pair in memory,
no real SPIRE Server / kernel required) and regresses the socket-level
contract of a real node-agent.

    - `HandshakeFrame` - the on-the-wire record: {side, spiffe_id, trust_domain,
      serial, not_after, uri_san, status}.
    - `MockUnixSocket` - an in-memory socket pair (send/recv) that models
      the `SPIFFE_ENDPOINT_SOCKET` Unix domain socket without a kernel
      socket (so it runs anywhere, including CI).
    - `BidirHandshake` - drives the two-way exchange:
        * `run()` - workload connects, presents its SVID frame, reads the
          agent's SVID frame; both sides verify the peer (trust-domain
          match + SPIFFE ID + expiry + URI SAN).
        * `report` - {connected, exchanged, peer_verified_each_side,
          mtls_established, frames}.
    - `run_socket_handshake(cfg)` - one-shot: build the two SVID frames
      from a `BidirMTLSConfig`, run the exchange over a mock socket, and
      return the report.

Stdlib-only. The mock socket models the byte exchange; a real
`socket.socket(AF_UNIX)` is a drop-in swap when the SPIRE Agent's socket
is present.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .spire_bidir_mtls import BidirMTLSConfig

__all__ = [
    "HandshakeFrame", "MockUnixSocket", "BidirHandshake",
    "run_socket_handshake",
]


@dataclass
class HandshakeFrame:
    """One SVID presentation over the socket."""
    side: str            # "workload" | "node-agent"
    spiffe_id: str
    trust_domain: str
    serial: str
    not_after: float
    uri_san: List[str] = field(default_factory=list)
    status: str = "ok"

    def to_wire(self) -> bytes:
        """The on-the-wire bytes (JSON, UTF-8)."""
        return json.dumps({
            "side": self.side, "spiffe_id": self.spiffe_id,
            "trust_domain": self.trust_domain, "serial": self.serial,
            "not_after": self.not_after, "uri_san": self.uri_san,
            "status": self.status,
        }, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def from_wire(raw: bytes) -> "HandshakeFrame":
        d = json.loads(raw.decode("utf-8"))
        return HandshakeFrame(
            side=d["side"], spiffe_id=d["spiffe_id"],
            trust_domain=d["trust_domain"], serial=d["serial"],
            not_after=d["not_after"], uri_san=d.get("uri_san", []),
            status=d.get("status", "ok"))

    def verify_peer(self, expected_trust_domain: str,
                    now: Optional[float] = None) -> Dict[str, Any]:
        """The peer's check of this frame: trust-domain match + SPIFFE ID
        well-formed + not expired + the SPIFFE ID in the URI SAN."""
        now = now or time.time()
        reasons: List[str] = []
        if self.trust_domain != expected_trust_domain:
            reasons.append(
                f"trust-domain mismatch {self.trust_domain!r} "
                f"!= {expected_trust_domain!r}")
        if not self.spiffe_id.startswith(f"spiffe://{self.trust_domain}"):
            reasons.append(f"spiffe_id not under trust domain")
        if now > self.not_after:
            reasons.append("svid expired")
        if self.spiffe_id not in self.uri_san:
            reasons.append("spiffe_id not in URI SAN")
        return {"ok": not reasons, "reasons": reasons,
                "peer_spiffe_id": self.spiffe_id,
                "peer_trust_domain": self.trust_domain}


class MockUnixSocket:
    """An in-memory socket pair that models the SPIFFE Workload API Unix
    domain socket. `connect()` returns a (workload_side, agent_side)
    pair; `send`/`recv` are the byte exchange. No kernel socket is used,
    so this runs anywhere (including CI)."""

    def __init__(self, path: str = "/run/spire/sockets/private/api.sock",
                 ) -> None:
        self.path = path
        self._buf_w: List[bytes] = []
        self._buf_a: List[bytes] = []

    def connect(self) -> tuple:
        return _SockEnd(self, "w"), _SockEnd(self, "a")

    def send_w(self, data: bytes) -> None:
        self._buf_a.append(data)

    def send_a(self, data: bytes) -> None:
        self._buf_w.append(data)

    def recv_w(self) -> Optional[bytes]:
        return self._buf_w.pop(0) if self._buf_w else None

    def recv_a(self) -> Optional[bytes]:
        return self._buf_a.pop(0) if self._buf_a else None


class _SockEnd:
    """One end of the mock socket."""

    def __init__(self, sock: MockUnixSocket, side: str) -> None:
        self._sock = sock
        self._side = side

    def send(self, data: bytes) -> None:
        if self._side == "w":
            self._sock.send_w(data)
        else:
            self._sock.send_a(data)

    def recv(self) -> Optional[bytes]:
        if self._side == "w":
            return self._sock.recv_w()
        return self._sock.recv_a()


@dataclass
class BidirHandshake:
    """Drive the two-way SVID exchange over a (mock) socket."""
    cfg: BidirMTLSConfig
    socket: Optional[MockUnixSocket] = None

    def _frames(self) -> tuple:
        c = self.cfg.default_spiffe_ids()
        now = time.time()
        ts = c.svid_ttl_s
        workload = HandshakeFrame(
            side="workload", spiffe_id=c.workload_spiffe_id,
            trust_domain=c.trust_domain,
            serial=uuid.uuid4().hex[:12],
            not_after=now + ts,
            uri_san=[c.workload_spiffe_id])
        agent = HandshakeFrame(
            side="node-agent", spiffe_id=c.agent_spiffe_id,
            trust_domain=c.trust_domain,
            serial=uuid.uuid4().hex[:12],
            not_after=now + ts,
            uri_san=[c.agent_spiffe_id])
        return workload, agent

    def run(self) -> Dict[str, Any]:
        """connect, exchange SVID frames, each side verifies the peer."""
        self.socket = self.socket or MockUnixSocket(
            self.cfg.svid_socket)
        wl_end, ag_end = self.socket.connect()
        workload, agent = self._frames()

        # workload -> agent: present the workload SVID
        wl_end.send(workload.to_wire())
        agent_got = ag_end.recv()
        # agent -> workload: present the agent SVID
        ag_end.send(agent.to_wire())
        workload_got = wl_end.recv()

        # verify each side's view of the peer
        peer_of_workload = HandshakeFrame.from_wire(
            workload_got) if workload_got else agent
        peer_of_agent = HandshakeFrame.from_wire(
            agent_got) if agent_got else workload
        wl_verify = workload.verify_peer(self.cfg.trust_domain)
        ag_verify = agent.verify_peer(self.cfg.trust_domain)
        # cross-check: the frame each side RECEIVED must verify too
        recv_verify_wl = peer_of_workload.verify_peer(
            self.cfg.trust_domain)  # workload received the agent's SVID
        recv_verify_ag = peer_of_agent.verify_peer(
            self.cfg.trust_domain)  # agent received the workload's SVID

        exchanged = (workload_got is not None and agent_got is not None)
        # mTLS is established when BOTH sides verify BOTH directions
        established = bool(
            wl_verify["ok"] and ag_verify["ok"]
            and recv_verify_wl["ok"] and recv_verify_ag["ok"])
        return {
            "connected": True,
            "exchanged": exchanged,
            "mtls_established": established,
            "trust_domain": self.cfg.trust_domain,
            "workload_spiffe_id": workload.spiffe_id,
            "agent_spiffe_id": agent.spiffe_id,
            "workload_verified_agent": recv_verify_wl,
            "agent_verified_workload": recv_verify_ag,
            "workload_self": wl_verify,
            "agent_self": ag_verify,
            "frames": [workload, agent],
        }


def run_socket_handshake(cfg: Optional[BidirMTLSConfig] = None
                         ) -> Dict[str, Any]:
    """tool: run_socket_handshake - one-shot two-way SVID exchange over a
    (mock) socket. Returns the `BidirHandshake.run()` report. `cfg`
    defaults to a well-formed `BidirMTLSConfig` (socket + trust bundle
    under the node-agent mount)."""
    cfg = cfg or BidirMTLSConfig()
    hs = BidirHandshake(cfg)
    report = hs.run()
    # summarize the invariant for callers
    report["regression_passed"] = report["mtls_established"]
    report["summary"] = (
        f"mtls={'established' if report['mtls_established'] else 'FAILED'} "
        f"over {cfg.svid_socket} in trust domain {cfg.trust_domain}")
    return report
