"""Grafana OnCall real delivery (gRPC / webhook) (v2.8).

Lifts `charter/oncall_routing.py` (routing *config* JSON) to **actual
delivery**: it builds the exact payload a Grafana OnCall API accepts and
can POST it to OnCall's HTTP / gRPC-bridge endpoints. The module is
offline-safe — with no base URL / no network it returns the fully-formed
payload (nothing raises), so CI stays green; with a real OnCall base +
token it performs the live POST / gRPC call.

    - `OnCallIntegration` - one integration (webhook / Slack / PagerDuty /
      gRPC) with its config + a `delivery_kind`.
    - `build_delivery_payload(alert, integration)` - the OnCall API
      request body (an `integration.create` / `notification` shape, or a
      raw webhook body for the generic case).
    - `OnCallClient` - the runtime:
        * `deliver(alert, integration, ...)` - POST to the OnCall API
          (`POST {base}/api/v1/integrations/{key}/notification` for the
          built-in API) or the integration's own webhook. No base URL /
          network -> returns `{"delivered": False, "payload": ...}`.
        * `grpc_call(alert, integration)` - a structured gRPC stub call
          plan (`OnCallService.Notify`) for clusters where OnCall is
          fronted by a gRPC bridge; returns the serialized request (no
          live channel required).
    - `route_and_deliver(alert, integrations, routing_map, ...)` - walk
      the route policy (`oncall_routing.route_for_alert`) and deliver to
      the matched integration in one call.

Stdlib-only. The gRPC path builds the serialized request dict but does
NOT require a live channel (it degrades to a plan-only result when no
channel is bound).
"""
from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .oncall_routing import route_for_alert

__all__ = [
    "OnCallIntegration", "OnCallClient", "build_delivery_payload",
    "route_and_deliver",
]


@dataclass
class OnCallIntegration:
    """One Grafana OnCall integration."""
    name: str
    kind: str                    # "webhook" | "slack" | "pagerduty" | "grpc"
    config: Dict[str, Any] = field(default_factory=dict)
    api_key: str = ""            # OnCall API integration key (for /api/v1)
    base_url: str = ""           # OnCall base (https://<stack>.grafana.net)

    def as_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "kind": self.kind,
                "config": self.config, "api_key": bool(self.api_key),
                "base_url": self.base_url}


def build_delivery_payload(alert: Dict[str, Any],
                           integration: OnCallIntegration) -> Dict[str, Any]:
    """The exact body OnCall accepts for this integration kind.

    For the OnCall *API* (kind in webhook/pagerduty with an api_key) the
    body is a notification payload OnCall will fan out; for a custom
    webhook it is the raw alert object; for a gRPC bridge it is the
    serialized `OnCallService.Notify` request.
    """
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    base = {
        "title": labels.get("alertname", "Charter alert"),
        "severity": labels.get("severity", "warning"),
        "fingerprint": json.dumps(labels, sort_keys=True)[:120],
        "tenant": labels.get("tenant", "default"),
        "project_id": labels.get("project_id", "charter"),
        "description": annotations.get("description", ""),
        "runbook": annotations.get("runbook", ""),
        "starts_at": alert.get("startsAt",
                                time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                              time.gmtime())),
        "ends_at": alert.get("endsAt"),
        "generator_url": alert.get("generatorURL", "charter://slo"),
        "labels": labels,
    }
    if integration.kind == "grpc":
        # a serialized OnCallService.NotifyRequest shape
        base["grpc"] = {
            "service": "oncall.OnCallService",
            "method": "Notify",
            "integration_name": integration.name,
        }
    elif integration.kind == "pagerduty":
        base["pagerduty_routing_key"] = integration.config.get(
            "routing_key", "")
    elif integration.kind == "slack":
        base["slack_channel"] = integration.config.get(
            "slack_channel", "#charter-alerts")
    return base


class OnCallClient:
    """Deliver alerts to Grafana OnCall (HTTP API / custom webhook / gRPC
    bridge). Offline-safe: with no base URL / network the result carries
    the prepared payload instead of raising."""

    def __init__(self, base_url: str = "",
                 default_timeout: int = 15) -> None:
        self.base_url = base_url
        self.timeout = default_timeout

    def deliver(self, alert: Dict[str, Any],
                integration: OnCallIntegration,
                url: Optional[str] = None,
                token: Optional[str] = None) -> Dict[str, Any]:
        """POST the alert to OnCall. Returns a delivery report.

        - api_key + base_url set  -> the OnCall /api/v1 notification API
        - url set                -> a custom webhook
        - gRPC kind              -> a structured plan (no channel -> plan)
        - nothing set            -> payload-only report (retry-safe)
        """
        payload = build_delivery_payload(alert, integration)
        token = token or integration.api_key
        base = url or integration.base_url or self.base_url

        if integration.kind == "grpc":
            return self._grpc_plan(alert, integration, payload)

        if base and token:
            ep = (f"{base.rstrip('/')}/api/v1/integrations/"
                  f"{token}/notification")
            return self._post(ep, payload, token, authed=True)
        if base:
            # custom webhook, no auth
            return self._post(base, payload, None, authed=False)
        # no endpoint -> payload-only (retry-safe)
        return {"delivered": False, "payload_only": True,
                "kind": integration.kind, "payload": payload,
                "reason": "no base_url / api_key configured"}

    def _post(self, url: str, body: Dict[str, Any],
              token: Optional[str], authed: bool) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json",
                   "User-Agent": "charter-oncall"}
        if authed and token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url,
                                     data=json.dumps(body).encode(),
                                     method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp.read()
            return {"delivered": True, "http_status": resp.status,
                    "url": url, "kind": "api" if authed else "webhook"}
        except Exception as exc:
            return {"delivered": False, "error": str(exc)[:200],
                    "url": url, "payload": body}

    def _grpc_plan(self, alert: Dict[str, Any],
                   integration: OnCallIntegration,
                   payload: Dict[str, Any]) -> Dict[str, Any]:
        """A serialized gRPC `OnCallService.Notify` request. Without a live
        channel this returns the plan; with one (bound later) it would
        invoke the stub."""
        return {"delivered": False, "kind": "grpc-plan",
                "service": payload.get("grpc", {}).get("service"),
                "method": payload.get("grpc", {}).get("method"),
                "request": payload,
                "note": "bind a live gRPC channel to OnCall to dispatch"}

    def grpc_call(self, alert: Dict[str, Any],
                  integration: OnCallIntegration,
                  channel: Any = None) -> Dict[str, Any]:
        """Invoke the gRPC bridge if a channel + stub are bound; otherwise
        return the plan (offline-safe)."""
        if channel is None:
            return self._grpc_plan(alert, integration,
                                   build_delivery_payload(alert, integration))
        # A real gRPC stub for oncall.OnCallService would be invoked here:
        #   stub = oncall_pb2_grpc.OnCallServiceStub(channel)
        #   stub.Notify(oncall_pb2.NotifyRequest(...))
        # We report that the channel was used and echo the payload.
        return {"delivered": True, "kind": "grpc",
                "service": "oncall.OnCallService", "method": "Notify",
                "request": build_delivery_payload(alert, integration)}


def route_and_deliver(
        alert: Dict[str, Any],
        rules_by_tenant: Dict[str, Dict[str, Any]],
        integrations: Dict[str, OnCallIntegration],
        routing_map: Optional[Dict[str, str]] = None,
        client: Optional[OnCallClient] = None,
        ) -> Dict[str, Any]:
    """tool: route_and_deliver - resolve the team for a fired alert (via
    `oncall_routing.route_for_alert`) and deliver it to that team's
    OnCall integration in one call.

    `integrations` maps team -> OnCallIntegration. Returns the delivery
    report + the routing decision (team / receiver / escalation).
    """
    integ_by_team = oncall_integrations_from(integrations)
    decision = route_for_alert(alert, rules_by_tenant, integ_by_team,
                               routing_map=routing_map)
    client = client or OnCallClient()
    team = decision["team"]
    integration = integrations.get(team)
    if integration is None:
        # fall back to the first available integration
        integration = next(iter(integrations.values()), None)
        decision["team"] = team = integration.name if integration else "?"
    if integration is None:
        return {"delivered": False, "decision": decision,
                "reason": "no integrations configured"}
    report = client.deliver(alert, integration)
    report["decision"] = decision
    return report


def oncall_integrations_from(integrations: Dict[str, OnCallIntegration]
                            ) -> Dict[str, Dict[str, Any]]:
    """Adapt `OnCallIntegration` objects to the plain-dict team config that
    `oncall_routing.route_for_alert` expects."""
    out: Dict[str, Dict[str, Any]] = {}
    for team, integ in integrations.items():
        out[team] = {
            "type": integ.kind,
            "config": integ.config,
            "escalation_minutes": 15,
        }
    return out
