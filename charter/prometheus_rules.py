"""Prometheus Alertmanager rule auto-generation (v2.5).

Lifts `charter/slo_alerts.py` (runtime alert delivery) to **rule generation**:
given the `charter_*` metrics already exported by `charter/otel_export.py`
(`charter_spans_total`, `charter_error_spans_total`,
`charter_tool_calls_total`, `charter_uptime_seconds`), this module emits a
valid **Prometheus `rules.yaml`** that Alertmanager / Prometheus can load
directly, with sensible SLO-aware expressions and annotation templates.

    - `alert_rules(...)` - a Prometheus `groups:` doc with:
        * high-error-rate rule (error spans / total spans > threshold)
        * tool-call burst rule (rate of a specific tool > limit)
        * low-uptime rule (charter_uptime_seconds < floor)
    - `alertmanager_provisioning(...)` - an Alertmanager `route` +
      `inhibit_rules` + `receivers` skeleton wired to the same alerts.
    - `render_provisioning_bundle(...)` - both docs in one dict, ready to be
      POSTed to Grafana's provisioning API or dropped on disk.

Stdlib-only. No network: the output is pure YAML-ready JSON (Prometheus
accepts YAML; JSON is a strict subset of YAML 1.2 so this loads anywhere
that accepts YAML provisioning files).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

__all__ = [
    "alert_rules", "alertmanager_provisioning", "render_provisioning_bundle",
]


def alert_rules(
        error_ratio: float = 0.05,
        error_for_minutes: int = 5,
        tool: str = "execute_in_sandbox",
        tool_rate_per_min: float = 60.0,
        uptime_floor_s: int = 30,
        project_id: str = "charter",
        extra_rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Generate a Prometheus `groups:` doc with charter SLO alert rules.

    Every rule carries `labels.severity` + `annotations.summary` /
    `annotations.description` / `annotations.runbook` so Grafana's alerting
    and Alertmanager both render them cleanly.
    """
    rules: List[Dict[str, Any]] = []

    # 1. High error ratio (error spans / total spans over a window)
    rules.append({
        "alert": "CharterHighErrorRate",
        "expr": (f"sum by (project_id) (increase(charter_error_spans_total{{project_id=\"{project_id}\"}}[{error_for_minutes}m])) "
                 f"/ sum by (project_id) (increase(charter_spans_total{{project_id=\"{project_id}\"}}[{error_for_minutes}m])) > {error_ratio}"),
        "for": f"{error_for_minutes}m",
        "labels": {"severity": "warning", "source": "charter",
                    "project_id": project_id},
        "annotations": {
            "summary": (f"High error ratio for {project_id} "
                        f"(>{error_ratio:.0%} over {error_for_minutes}m)"),
            "description": (
                "charter_error_spans_total / charter_spans_total has been "
                "above the threshold for {{ $duration }}."
                ),
            "runbook": "docs/runbooks/high-error-rate.md",
        },
    })

    # 2. Tool-call burst (rate of a specific tool)
    rules.append({
        "alert": "CharterToolCallBurst",
        "expr": (f"sum by (tool) (increase(charter_tool_calls_total{{tool=\"{tool}\"}}[1m])) "
                 f"> {tool_rate_per_min}"),
        "for": "2m",
        "labels": {"severity": "warning", "source": "charter",
                    "tool": tool},
        "annotations": {
            "summary": (f"Burst of {tool} calls "
                        f"(>{tool_rate_per_min:.0f}/min)"),
            "description": (
                "charter_tool_calls_total for tool={{ $labels.tool }} "
                "exceeded the per-minute threshold."
            ),
            "runbook": "docs/runbooks/tool-call-burst.md",
        },
    })

    # 3. Low uptime (the agent has been down)
    rules.append({
        "alert": "CharterLowUptime",
        "expr": f"charter_uptime_seconds < {uptime_floor_s}",
        "for": "1m",
        "labels": {"severity": "critical", "source": "charter"},
        "annotations": {
            "summary": "Charter orchestrator uptime below floor",
            "description": (
                f"charter_uptime_seconds has dropped below "
                f"{uptime_floor_s}s - the agent may be down or restarting."
            ),
            "runbook": "docs/runbooks/low-uptime.md",
        },
    })

    if extra_rules:
        rules.extend(extra_rules)

    return {
        "groups": [{
            "name": "charter-slo",
            "interval": "30s",
            "rules": rules,
        }],
    }


def alertmanager_provisioning(
        receiver: str = "charter-oncall",
        pagerduty_routing_key: str = "",
        webhook_url: str = "",
        escalation_minutes: int = 10,
        extra_receivers: Optional[List[Dict[str, Any]]] = None
        ) -> Dict[str, Any]:
    """Generate an Alertmanager `route` + `receivers` + `inhibit_rules`
    skeleton wired to the charter SLO alerts."""
    receivers: List[Dict[str, Any]] = []
    if webhook_url:
        receivers.append({
            "name": receiver,
            "webhook_configs": [{"url": webhook_url}],
        })
    elif pagerduty_routing_key:
        receivers.append({
            "name": receiver,
            "pagerduty_configs": [{
                "routing_key": pagerduty_routing_key,
                "severity": "{{ .Labels.severity }}",
            }],
        })
    else:
        receivers.append({
            "name": receiver,
            "webhook_configs": [{"url": "http://localhost:9093/dispatch"}],
        })
    if extra_receivers:
        receivers.extend(extra_receivers)

    return {
        "route": {
            "receiver": receiver,
            "group_by": ["alertname", "project_id"],
            "group_wait": "30s",
            "group_interval": "5m",
            "repeat_interval": f"{escalation_minutes}m",
            "routes": [
                {
                    "match": {"severity": "critical"},
                    "receiver": receiver,
                    "repeat_interval": f"{max(1, escalation_minutes // 2)}m",
                },
            ],
        },
        "inhibit_rules": [
            {
                "source_matchers": ["severity=\"critical\""],
                "target_matchers": ["severity=\"warning\""],
                "equal": ["alertname", "project_id"],
            },
        ],
        "receivers": receivers,
    }


def render_provisioning_bundle(
        error_ratio: float = 0.05,
        error_for_minutes: int = 5,
        tool: str = "execute_in_sandbox",
        tool_rate_per_min: float = 60.0,
        uptime_floor_s: int = 30,
        project_id: str = "charter",
        receiver: str = "charter-oncall",
        pagerduty_routing_key: str = "",
        webhook_url: str = "",
        escalation_minutes: int = 10,
        extra_rules: Optional[List[Dict[str, Any]]] = None,
        extra_receivers: Optional[List[Dict[str, Any]]] = None
        ) -> Dict[str, str]:
    """tool: render_provisioning_bundle - one-shot rules + Alertmanager YAML.

    Returns {"prometheus_rules": <YAML-ready JSON str>,
             "alertmanager_config": <YAML-ready JSON str>} ready to be
    dropped into Grafana / Prometheus / Alertmanager provisioning.
    """
    rules = alert_rules(
        error_ratio=error_ratio, error_for_minutes=error_for_minutes,
        tool=tool, tool_rate_per_min=tool_rate_per_min,
        uptime_floor_s=uptime_floor_s, project_id=project_id,
        extra_rules=extra_rules)
    am = alertmanager_provisioning(
        receiver=receiver, pagerduty_routing_key=pagerduty_routing_key,
        webhook_url=webhook_url, escalation_minutes=escalation_minutes,
        extra_receivers=extra_receivers)
    return {
        "prometheus_rules": json.dumps(rules, indent=2, ensure_ascii=False),
        "alertmanager_config": json.dumps(am, indent=2, ensure_ascii=False),
    }
