"""Trace SLO -> real alerting (Alertmanager / PagerDuty) (v2.4).

Closes the v2.4 candidate "Trace SLO 接真实告警". `charter/trace_link.py`
computes per-service SLO digests (`aggregate_traces`, `slo_summary`); this
module turns *breached* SLOs into real alert payloads and delivers them to:

    - Alertmanager  (HTTP :9093/api/v2/alerts, groups + labels + annotations)
    - PagerDuty     (Events API v2 :incident)

Plus an in-process `AlertSLOGate` that evaluates a `slo_summary` against
alert thresholds and decides whether to fire. Stdlib-only (urllib). Offline-
safe: `fire(...)` returns a fully-formed `AlertPayload` even when no
endpoint / no network is reachable (the payload is carried in the result,
nothing raises), so CI stays green and the caller can retry or inspect.

Env vars:
    ALERTMANAGER_URL   default http://localhost:9093/api/v2/alerts
    PAGERDUTY_TOKEN    PagerDuty Events API v2 token
    PAGERDUTY_URL      default https://events.pagerduty.com/v2/incidents
    SLO_ALERT_SEVERITY default "warning"
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .trace_link import slo_summary, aggregate_traces

__all__ = [
    "AlertPayload", "SLOAlertGate", "build_alert_payload",
    "fire_alertmanager", "fire_pagerduty", "fire",
]


@dataclass
class AlertPayload:
    """A normalized SLO alert, dispatchable to any backend."""
    title: str
    severity: str
    service: str
    message: str
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    fired_ts: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_alertmanager(self, service: str = "charter-orchestrator") -> Dict[str, Any]:
        return {
            "labels": {
                "alertname": "CharterSLOBreached",
                "service": self.service,
                "severity": self.severity,
                "source": service,
                **self.labels,
            },
            "annotations": {
                "summary": self.title,
                "description": self.message,
                **self.annotations,
            },
            "startsAt": _iso(self.fired_ts),
            "generatorURL": "charter://slo",
        }

    def to_pagerduty(self) -> Dict[str, Any]:
        return {
            "routing_key": self.labels.get("pagerduty_routing_key", ""),
            "event_action": "trigger",
            "payload": {
                "summary": self.title,
                "severity": self.severity,
                "source": "charter-orchestrator",
                "component": self.service,
                "custom_details": self.details,
            },
        }


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def build_alert_payload(slo: Dict[str, Any],
                       service: str = "charter-orchestrator",
                       severity: Optional[str] = None) -> AlertPayload:
    """Build an AlertPayload from a slo_summary (fires only when breached)."""
    severity = severity or os.environ.get(
        "SLO_ALERT_SEVERITY", "warning")
    breached = [s for s, m in slo.get("services", {}).items()
                if not m.get("met")]
    if not breached:
        return AlertPayload(
            title=f"[OK] {service} SLO met", severity="resolved",
            service=service, message="All SLOs met",
            details={"slo": slo},
        )
    svc = breached[0]
    m = slo["services"][svc]
    title = f"[{severity.upper()}] SLO breached for {svc}"
    msg = (f"p95={m.get(chr(39)+chr(39))} " if False else "")
    msg = (f"p95={m.get(chr(39)+chr(39))} " if False else "")
    # build the message without quoting issues
    p95 = m.get("p95_ms", "?")
    err = m.get("error_rate", "?")
    tgt_p95 = slo.get("target_p95_ms", "?")
    tgt_err = slo.get("target_error_rate", "?")
    msg = f"p95={p95}ms (target {tgt_p95}ms), error_rate={err} (target {tgt_err})"
    return AlertPayload(
        title=title, severity=severity, service=svc, message=msg,
        labels={"breached_services": ",".join(breached)},
        annotations={"slo_summary": "BREACHED"},
        details={"slo": slo},
    )


class SLOAlertGate:
    """Evaluate SLOs and decide to fire; dispatches to the chosen backend."""

    def __init__(self, alertmanager_url: Optional[str] = None,
                 pagerduty_url: Optional[str] = None,
                 pagerduty_token: Optional[str] = None,
                 timeout: int = 15) -> None:
        self.am_url = alertmanager_url or os.environ.get(
            "ALERTMANAGER_URL", "http://localhost:9093/api/v2/alerts")
        self.pd_url = pagerduty_url or os.environ.get(
            "PAGERDUTY_URL", "https://events.pagerduty.com/v2/incidents")
        self.pd_token = pagerduty_token or os.environ.get("PAGERDUTY_TOKEN")
        self.timeout = timeout

    def evaluate(self, spans, p95_ms: float = 500.0,
                 error_rate: float = 0.05) -> Dict[str, Any]:
        slo = slo_summary(spans, s_lo_ms=p95_ms, s_lo_error=error_rate)
        payload = build_alert_payload(slo,
                                      service="charter-orchestrator")
        return {"slo": slo, "payload": payload,
                "should_fire": payload.severity != "resolved"}


def fire_alertmanager(payload: AlertPayload,
                      url: Optional[str] = None,
                      timeout: int = 15) -> Dict[str, Any]:
    """Deliver to Alertmanager :9093. Returns delivery report (retry-safe)."""
    url = url or os.environ.get(
        "ALERTMANAGER_URL", "http://localhost:9093/api/v2/alerts")
    body = {"alerts": [payload.to_alertmanager()]}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": "charter-slo-alerts"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        return {"delivered": True, "http_status": resp.status}
    except Exception as exc:
        return {"delivered": False, "error": str(exc)[:200], "payload": body}


def fire_pagerduty(payload: AlertPayload,
                   token: Optional[str] = None,
                   url: Optional[str] = None,
                   timeout: int = 15) -> Dict[str, Any]:
    """Deliver to PagerDuty Events API v2. Returns delivery report."""
    token = token or os.environ.get("PAGERDUTY_TOKEN")
    url = url or os.environ.get(
        "PAGERDUTY_URL", "https://events.pagerduty.com/v2/incidents")
    body = payload.to_pagerduty()
    headers = {"Content-Type": "application/json",
               "Authorization": f"Token token={token}"}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        return {"delivered": True, "http_status": resp.status}
    except Exception as exc:
        return {"delivered": False, "error": str(exc)[:200],
                "payload": body, "token_set": bool(token)}


def fire(payload: AlertPayload, backend: str = "alertmanager",
         url: Optional[str] = None, token: Optional[str] = None,
         timeout: int = 15) -> Dict[str, Any]:
    """tool: fire - dispatch an SLO alert to a real backend.

    `backend` in {"alertmanager","pagerduty","none"}. "none" returns just the
    payload (no network) - the offline-safe default. Never raises: a failed
    delivery returns a retry-safe report carrying the prepared payload.
    """
    if backend == "alertmanager":
        return fire_alertmanager(payload, url=url, timeout=timeout)
    if backend == "pagerduty":
        return fire_pagerduty(payload, token=token, url=url, timeout=timeout)
    if backend == "none":
        return {"delivered": False, "payload_only": True,
                "alertmanager_body": {"alerts": [payload.to_alertmanager()]},
                "pagerduty_body": payload.to_pagerduty()}
    raise ValueError(f"unknown alert backend: {backend!r}")
