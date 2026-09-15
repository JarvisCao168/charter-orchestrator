"""Mimir -> Grafana OnCall alert routing (v2.7).

Lifts `charter/mimir_multitenant.py` (rule + data-source provisioning) to
**alert routing**: when a tenant-scoped Mimir rule fires, route it to the
right Grafana OnCall integration (a Slack channel / PagerDuty / webhook /
escalation policy) based on the alert's labels. This module emits:

    - `oncall_integrations(...)` - Grafana OnCall integration configs
      (webhooks, Slack, PagerDuty, escalation) keyed per team/tenant.
    - `oncall_route_policy(alert_rules, integrations, routing_map)` - a
      Grafana/Alertmanager `route` tree that maps
      {tenant, severity, alertname} -> a receiver (integration), with
      per-severity escalation windows.
    - `oncall_provisioning_bundle(...)` - one-shot: integrations + route
      + inhibit + silences, as JSON ready to POST to Grafana OnCall's
      provisioning API (or drop into an oncall_config.yaml).

Stdlib-only. No network: the output is pure JSON (YAML subset). The live
routing happens in Grafana OnCall; this module only produces the routing
artifacts.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

__all__ = [
    "oncall_integrations", "oncall_route_policy",
    "oncall_provisioning_bundle", "route_for_alert",
]


def oncall_integrations(
        teams: Optional[Dict[str, Dict[str, Any]]] = None,
        default_webhook: str = "http://localhost:9093/dispatch",
        default_slack_channel: str = "#charter-alerts",
        default_pagerduty_routing_key: str = "",
        ) -> Dict[str, Dict[str, Any]]:
    """tool: oncall_integrations - Grafana OnCall integration configs per team.

    `teams` maps team_name -> {slack_channel, pagerduty_routing_key,
    webhook, escalation_minutes}. Omitted keys fall back to the defaults.
    Returns {team: {"name", "type", "config": {...}}}.
    """
    teams = teams or {}
    out: Dict[str, Dict[str, Any]] = {}
    for team, cfg in teams.items():
        cfg = cfg or {}
        entry: Dict[str, Any] = {
            "name": team,
            "type": "webhook" if cfg.get("webhook") else "slack",
            "config": {},
            "escalation_minutes": cfg.get("escalation_minutes", 15),
        }
        if cfg.get("slack_channel"):
            entry["config"]["slack_channel"] = cfg["slack_channel"]
        if cfg.get("pagerduty_routing_key"):
            entry["type"] = "pagerduty"
            entry["config"]["routing_key"] = cfg["pagerduty_routing_key"]
        if cfg.get("webhook"):
            entry["type"] = "webhook"
            entry["config"]["url"] = cfg["webhook"]
        # fill defaults
        if entry["type"] == "slack" and not entry["config"].get("slack_channel"):
            entry["config"]["slack_channel"] = default_slack_channel
        if entry["type"] == "webhook" and not entry["config"].get("url"):
            entry["config"]["url"] = default_webhook
        out[team] = entry
    return out


def oncall_route_policy(
        rules_by_tenant: Dict[str, Dict[str, Any]],
        integrations: Dict[str, Dict[str, Any]],
        routing_map: Optional[Dict[str, str]] = None,
        common_team: str = "charter-oncall",
        ) -> Dict[str, Any]:
    """tool: oncall_route_policy - an Alertmanager/Grafana `route` tree.

    `routing_map` maps tenant (or "default") -> team name. Each tenant's
    SLO alerts route to that team's integration; severity=critical routes
    with a tighter escalation. Returns {"route": {...}}.
    """
    routing_map = routing_map or {}
    team_for: Dict[str, str] = {}
    for tenant in rules_by_tenant:
        team_for[tenant] = routing_map.get(tenant, common_team)

    routes: List[Dict[str, Any]] = []
    for tenant, team in team_for.items():
        integrations_cfg = integrations.get(team, {})
        routes.append({
            "matchers": [f"tenant={tenant}"],
            "receiver": team,
            "group_by": ["alertname", "tenant"],
            "group_wait": "30s",
            "repeat_interval": f"{integrations_cfg.get('escalation_minutes', 15)}m",
            "routes": [
                {
                    "matchers": ['severity="critical"'],
                    "receiver": team,
                    "repeat_interval": "5m",
                },
            ],
        })
    return {
        "route": {
            "receiver": common_team,
            "group_by": ["alertname"],
            "group_wait": "30s",
            "group_interval": "5m",
            "repeat_interval": "1h",
            "routes": routes,
        },
        "team_for": team_for,
    }


def oncall_provisioning_bundle(
        rules_by_tenant: Optional[Dict[str, Dict[str, Any]]] = None,
        teams: Optional[Dict[str, Dict[str, Any]]] = None,
        routing_map: Optional[Dict[str, str]] = None,
        inhibit: bool = True,
        default_webhook: str = "http://localhost:9093/dispatch",
        ) -> Dict[str, str]:
    """tool: oncall_provisioning_bundle - one-shot OnCall routing bundle.

    Returns {"integrations", "route", "inhibit_rules", "silences"} as
    JSON strings, ready to POST to Grafana OnCall's provisioning API or
    drop into oncall_config.yaml.
    """
    rules_by_tenant = rules_by_tenant or {}
    integrations = oncall_integrations(
        teams=teams, default_webhook=default_webhook)
    policy = oncall_route_policy(rules_by_tenant, integrations,
                                routing_map=routing_map)
    common = policy["route"].get("receiver", "charter-oncall")
    def _receiver_cfg(name: str, c: Dict[str, Any]) -> Dict[str, Any]:
        if c.get("type") == "slack":
            return {"name": name,
                    "slack_configs": [{"channel": c["config"].get(
                        "slack_channel", "#charter-alerts"),
                        "send_resolved": True}]}
        if c.get("type") == "pagerduty":
            return {"name": name,
                    "pagerduty_configs": [{"routing_key": c["config"].get(
                        "routing_key", ""),
                        "severity": "{{ .Labels.severity }}"}]}
        # webhook (and unknown types fall back to a webhook)
        return {"name": name,
                "webhook_configs": [{"url": c["config"].get(
                    "url", default_webhook)}]}

    receivers: List[Dict[str, Any]] = []
    if integrations:
        for team, c in integrations.items():
            receivers.append(_receiver_cfg(team, c))
    else:
        receivers = [{"name": common,
                       "webhook_configs": [{"url": default_webhook}]}]

    am_config: Dict[str, Any] = {
        "route": policy["route"],
        "receivers": receivers,
    }
    if inhibit:
        am_config["inhibit_rules"] = [
            {"source_matchers": ['severity="critical"'],
             "target_matchers": ['severity="warning"'],
             "equal": ["alertname", "tenant"]},
        ]
    am_config["silences"] = []
    return {
        "integrations": json.dumps(integrations, indent=2),
        "oncall_config": json.dumps(am_config, indent=2),
        "route": json.dumps(policy["route"], indent=2),
        "team_for": json.dumps(policy["team_for"], indent=2),
    }


def route_for_alert(alert: Dict[str, Any],
                    rules_by_tenant: Dict[str, Dict[str, Any]],
                    integrations: Dict[str, Dict[str, Any]],
                    routing_map: Optional[Dict[str, str]] = None
                    ) -> Dict[str, Any]:
    """tool: route_for_alert - which receiver/team a fired alert routes to.

    Given a fired alert (with `labels.tenant` + `labels.severity`), walk
    the route policy and return {team, receiver, matchers_used,
    escalation_minutes}.
    """
    routing_map = routing_map or {}
    tenant = alert.get("labels", {}).get("tenant", "default")
    team = routing_map.get(tenant, "charter-oncall")
    if team not in integrations:
        team = "charter-oncall" if "charter-oncall" in integrations \
            else (list(integrations)[0] if integrations else "charter-oncall")
    cfg = integrations.get(team, {})
    escalation = cfg.get("escalation_minutes", 15)
    severity = alert.get("labels", {}).get("severity", "warning")
    if severity == "critical":
        escalation = min(escalation, 5)
    return {
        "alert": alert.get("labels", {}).get("alertname", "?"),
        "tenant": tenant,
        "team": team,
        "receiver": team,
        "escalation_minutes": escalation,
        "severity": severity,
    }
