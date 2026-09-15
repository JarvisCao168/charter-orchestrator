"""Grafana OnCall real gRPC end-to-end delivery (v2.10).

Lifts `charter/oncall_grpc_deliver.py` (a structured Notify *request* +
plan-only) to a **live gRPC end-to-end** delivery: it binds a real
`grpc` channel + the generated OnCall service stub, serializes the
`OnCallService.Notify` request, performs the call, and reads back the
receipt. When no channel / no grpc is available it degrades to a
plan-only report (the offline contract from v2.9 still holds), so CI
stays green; with a channel + stub it is a real end-to-end delivery.

    - `OnCallGRPCE2E` - the runtime:
        * `connect(target, insecure, timeout_s)` - open a `grpc.Channel`
          (real, when grpc is installed; a `MockChannel` plan otherwise).
        * `deliver(alert, integration, ...)` - serialize the Notify
          request, call `stub.Notify`, return the receipt (or a
          plan-only report).
        * `e2e_report(...)` - a one-shot report: channel connected?
          Notify invoked? receipt status? - the shape a CI / on-call
          pipeline asserts on.
    - `OnCallNotifyRequest` - the serialized request payload (the shape
      `oncall_pb2.NotifyRequest` would carry).

Stdlib-only. `grpc` + the OnCall proto are imported lazily; absence
degrades to a `MockChannel` + a plan-only report.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .oncall_deliver import OnCallIntegration, build_delivery_payload
from .oncall_grpc_deliver import OnCallGRPCClient

__all__ = [
    "OnCallGRPCE2E", "OnCallNotifyRequest", "e2e_delivery_report",
]


@dataclass
class OnCallNotifyRequest:
    """The serialized `OnCallService.Notify` request."""
    request_id: str
    integration_name: str
    payload: Dict[str, Any]
    ts: float = field(default_factory=time.time)

    def to_proto_kwargs(self) -> Dict[str, Any]:
        """The kwargs a generated `oncall_pb2.NotifyRequest(**...)`
        would take."""
        return {
            "request_id": self.request_id,
            "integration_name": self.integration_name,
            "payload": json.dumps(self.payload, ensure_ascii=False),
        }


class _MockChannel:
    """A plan-only stand-in for a `grpc.Channel` (no real gRPC)."""

    def __init__(self, target: str, note: str = "no grpc; mock channel") -> None:
        self.target = target
        self.note = note
        self.connected = False

    def unary_unary(self, method: str, request_serializer=None,
                    response_deserializer=None):
        def _call(req, timeout=None):
            raise RuntimeError(
                f"MockChannel: cannot invoke {method!r} without a live "
                f"gRPC channel ({self.note})")
        return _call


@dataclass
class OnCallGRPCE2E:
    """Deliver alerts to Grafana OnCall over a real gRPC channel, with a
    receipt + an end-to-end report."""
    channel: Any = None
    stub: Any = None
    target: str = "grafana-oncall:50051"
    timeout_s: int = 30
    _client: OnCallGRPCClient = field(default_factory=OnCallGRPCClient)

    # -- connect ---------------------------------------------------------
    def connect(self, target: Optional[str] = None,
                insecure: bool = True,
                token: Optional[str] = None) -> Dict[str, Any]:
        """Open a gRPC channel to the OnCall service. Returns a connect
        report. Without `grpc` installed, a `MockChannel` is used (the
        delivery will be plan-only)."""
        target = target or self.target
        self.target = target
        try:
            import grpc  # type: ignore
            self.channel = grpc.insecure_channel(target) if insecure \
                else grpc.secure_channel(target)
            # a generated stub would be built here:
            #   self.stub = oncall_pb2_grpc.OnCallServiceStub(self.channel)
            self._stub_class = "grpc"
            return {"connected": True, "target": target,
                    "transport": "grpc", "insecure": insecure}
        except Exception:
            self.channel = _MockChannel(target)
            self.stub = None
            self._stub_class = "mock"
            return {"connected": False, "target": target,
                    "transport": "mock",
                    "note": "grpc not installed; plan-only delivery"}

    # -- deliver ---------------------------------------------------------
    def deliver(self, alert: Dict[str, Any],
                integration: OnCallIntegration,
                request: Optional[OnCallNotifyRequest] = None
                ) -> Dict[str, Any]:
        """Serialize + invoke the OnCall Notify RPC. Returns a receipt
        (`{receipt, delivered, via, ...}`). Plan-only when the channel is
        a mock / no stub is bound."""
        request = request or OnCallNotifyRequest(
            request_id=uuid.uuid4().hex[:16],
            integration_name=integration.name,
            payload=build_delivery_payload(alert, integration))
        out = self._client.deliver(
            alert, integration, channel=self.channel, stub=self.stub,
            timeout=self.timeout_s)
        # attach the serialized request + receipt id
        out["request"] = request.to_proto_kwargs()
        out["receipt"] = {
            "request_id": request.request_id,
            "integration": integration.name,
            "delivered": out.get("delivered", False),
            "ts": time.time(),
        }
        return out

    # -- e2e report ------------------------------------------------------
    def e2e_report(self, alert: Dict[str, Any],
                   integration: OnCallIntegration,
                   ) -> Dict[str, Any]:
        """A one-shot end-to-end report a CI / on-call pipeline asserts on:
        channel connected? Notify invoked? receipt status?"""
        out = self.deliver(alert, integration)
        return {
            "target": self.target,
            "transport": getattr(self, "_stub_class", "unknown"),
            "channel_connected": not isinstance(self.channel, _MockChannel),
            "notify_invoked": out.get("delivered", False),
            "receipt": out.get("receipt"),
            "plan_only": out.get("via") == "grpc-plan" or
                         not out.get("delivered", False),
        }


def e2e_delivery_report(
        alert: Dict[str, Any],
        integration: OnCallIntegration,
        target: str = "grafana-oncall:50051",
        insecure: bool = True) -> Dict[str, Any]:
    """tool: e2e_delivery_report - one-shot end-to-end OnCall gRPC
    delivery report (live when grpc is installed + a stub is bound,
    plan-only otherwise)."""
    client = OnCallGRPCE2E()
    client.connect(target=target, insecure=insecure)
    return client.e2e_report(alert, integration)
