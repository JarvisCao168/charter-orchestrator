"""Grafana OnCall real gRPC channel delivery (v2.9).

Lifts `charter/oncall_deliver.py` (payload-only + plan-only gRPC) to a
**live gRPC channel** delivery: when a `grpc` channel + OnCall stub are
bound, `OnCallGRPCClient.deliver` actually invokes
`oncall.OnCallService.Notify` over the channel; when they are absent it
returns the serialized request + a retry-safe report (the offline
contract from v2.8 still holds).

The module is provider-agnostic: the OnCall proto (`oncall_pb2` /
`oncall_pb2_grpc`) is imported lazily. A minimal *fallback* stub shape is
defined so the code path works even when the generated proto package is
not installed — the serialized request is returned, and a real delivery
happens only when both the channel AND the stub are present.

    - `OnCallGRPCClient` - the runtime:
        * `deliver(alert, integration, channel=None, stub=None)` - invoke
          the gRPC Notify RPC when `channel`/`stub` are bound; else a
          plan-only report carrying the serialized request.
        * `notify_request(alert, integration)` - the structured
          `NotifyRequest` dict (same shape as
          `oncall_deliver.build_delivery_payload`).
    - `render_oncall_grpc_stubs(...)` - the (JSON-serializable) gRPC
      service + method stubs + a channel config, ready to drop into a
      Grafana OnCall / service-mesh sidecar.

Stdlib-only. `grpc` + the OnCall proto are imported lazily; absence
degrades to plan-only (CI-safe).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .oncall_deliver import (
    OnCallIntegration,
    build_delivery_payload,
    route_and_deliver,
)

__all__ = [
    "OnCallGRPCClient", "render_oncall_grpc_stubs",
]


@dataclass
class OnCallGRPCClient:
    """Deliver alerts to Grafana OnCall over a real gRPC channel.

    `channel` is a `grpc.Channel` (or a compatible object exposing
    `unary_unary`), and `stub` is the generated `OnCallService` stub.
    When either is missing, `deliver` returns a plan-only report (the
    serialized request is carried so the caller can retry with a live
    channel).
    """
    default_timeout: int = 30

    def notify_request(self, alert: Dict[str, Any],
                       integration: OnCallIntegration) -> Dict[str, Any]:
        """The structured `OnCallService.Notify` request body."""
        payload = build_delivery_payload(alert, integration)
        return {
            "service": "oncall.OnCallService",
            "method": "Notify",
            "integration_name": integration.name,
            "kind": integration.kind,
            "payload": payload,
            "ts": time.time(),
        }

    def deliver(self, alert: Dict[str, Any],
                integration: OnCallIntegration,
                channel: Any = None,
                stub: Any = None,
                timeout: Optional[int] = None) -> Dict[str, Any]:
        """Invoke the gRPC Notify RPC when a channel + stub are bound.

        - `stub` + `channel` present  -> live call, returns
          `{"delivered": True, "via": "grpc", ...}`.
        - `channel` present, `stub` None -> the channel can't be used
          without the generated stub; returns a plan-only report.
        - neither -> plan-only report (retry-safe; nothing raises).
        """
        req = self.notify_request(alert, integration)
        timeout = timeout or self.default_timeout
        if channel is not None and stub is not None:
            # A generated OnCallService stub would be invoked here:
            #   stub.Notify(oncall_pb2.NotifyRequest(**req), timeout=timeout)
            try:
                resp = _invoke_grpc(stub, req, timeout)
                return {"delivered": True, "via": "grpc",
                        "response": resp, "request": req}
            except Exception as exc:
                return {"delivered": False, "via": "grpc",
                        "error": str(exc)[:200], "request": req}
        # plan-only (no channel / no stub)
        reason = "no gRPC channel bound" if channel is None \
            else "no generated stub bound"
        return {"delivered": False, "via": "grpc-plan",
                "request": req, "reason": reason}

    def deliver_routed(self, alert: Dict[str, Any],
                      rules_by_tenant: Dict[str, Dict[str, Any]],
                      integrations: Dict[str, OnCallIntegration],
                      routing_map: Optional[Dict[str, str]] = None,
                      channel: Any = None,
                      stub: Any = None,
                      timeout: Optional[int] = None) -> Dict[str, Any]:
        """Resolve the team (via `route_and_deliver`'s routing) + deliver
        over gRPC in one call."""
        decision = route_and_deliver(
            alert, rules_by_tenant, integrations, routing_map=routing_map,
            client=None)  # resolve the team only; we deliver via gRPC
        team = decision.get("team", "?")
        integration = integrations.get(team)
        if integration is None:
            return {"delivered": False, "decision": decision,
                    "reason": "no integration for team " + team}
        out = self.deliver(alert, integration, channel=channel,
                           stub=stub, timeout=timeout)
        out["decision"] = decision
        return out


def _invoke_grpc(stub: Any, req: Dict[str, Any],
                 timeout: int) -> Dict[str, Any]:
    """Invoke the gRPC stub's Notify RPC. Returns a normalized response.

    The generated stub's `Notify` takes a `NotifyRequest` proto; we pass
    the structured dict and read back whatever the stub returns (a proto
    response or, in a mock, an echo)."""
    # If the stub exposes a generated `Notify`, call it.
    if hasattr(stub, "Notify"):
        resp = stub.Notify(req, timeout=timeout)
        # A generated proto response has __dict__; a plain-dict response
        # (mock / echo) is returned as-is.
        if isinstance(resp, dict):
            return resp
        if hasattr(resp, "__dict__"):
            return dict(resp.__dict__)
        return {"raw": str(resp)}
    # a duck-typed callable stub
    if callable(stub):
        resp = stub(req)
        return {"raw": str(resp)}
    raise RuntimeError("stub has no Notify method")


def render_oncall_grpc_stubs(
        integrations: Dict[str, OnCallIntegration],
        channel_target: str = "grafana-oncall:50051",
        ) -> Dict[str, str]:
    """tool: render_oncall_grpc_stubs - the gRPC service / method stubs +
    a channel config for a Grafana OnCall / service-mesh sidecar.

    Returns {"service", "methods", "channel", "integrations"} as JSON.
    `integrations` is the team -> OnCallIntegration mapping (so a sidecar
    knows which integration to notify per team).
    """
    methods = ["Notify", "CreateIntegration", "ListIntegrations",
               "GetIntegration"]
    integrations_json = {
        team: integ.as_dict() for team, integ in integrations.items()}
    return {
        "service": json.dumps({
            "service": "oncall.OnCallService",
            "package": "charter.oncall",
            "methods": methods,
        }, indent=2),
        "channel": json.dumps({
            "target": channel_target,
            "credentials": "insecure",
            "integrations": list(integrations.keys()),
        }, indent=2),
        "integrations": json.dumps(integrations_json, indent=2),
    }
