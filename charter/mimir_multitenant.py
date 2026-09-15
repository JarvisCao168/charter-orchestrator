"""Grafana Mimir multi-tenant + label propagation (v2.6).

Lifts `charter/prometheus_rules.py` (single-tenant rules) to a **Mimir
multi-tenant** setup: each project / team gets its own Mimir user (tenant
prefix), metrics are label-propagated so tenant + project + service are
carried into every time series, and the provisioning is generated for
Grafana's Mimir / Loki / Tempo data sources plus the tenant-scoped rules.

    - `mimir_tenants(projects, default_prefix)` - map project -> Mimir
      tenant user (a stable per-project prefix, e.g. `charter-<project>`).
    - `tenant_rules(project, tenant, ...)` - a Prometheus `groups:` doc
      scoped to one tenant, with tenant + project labels propagated into
      every rule's `for` window + `labels` + `annotations`.
    - `label_propagation_config(metrics_prefix, extra_labels)` - the Mimir
      distributor/ingester label-propagation config (per-tenant,
      `per_tenant_override` shape) that adds a fixed set of labels to
      ingested time series.
    - `mimir_provisioning_bundle(projects, ...)` - one-shot: tenants +
      per-tenant rules + label propagation + Grafana Mimir/Loki/Tempo data
      sources, all as JSON-ready docs.

Stdlib-only. No network: the output is pure JSON (a YAML subset) ready to
drop into Grafana / Mimir provisioning.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

__all__ = [
    "mimir_tenants", "tenant_rules", "label_propagation_config",
    "mimir_provisioning_bundle",
]


def _tenant_for(project: str, prefix: str = "charter") -> str:
    """Stable Mimir tenant user name for a project."""
    safe = "".join(ch if (ch.isalnum() or ch in "-_") else "-"
                    for ch in project.lower().strip())
    safe = safe.strip("-_") or "default"
    return f"{prefix}-{safe}"


def mimir_tenants(projects: List[str],
                  prefix: str = "charter",
                  ) -> Dict[str, str]:
    """tool: mimir_tenants - map each project to a Mimir tenant user.

    Returns {project: tenant_user}. Mimir multi-tenancy scopes every
    request (query / ingester / distributor) by this user, so project
    A's metrics are invisible to project B.
    """
    return {p: _tenant_for(p, prefix) for p in projects}


def tenant_rules(
        project: str,
        tenant: Optional[str] = None,
        error_ratio: float = 0.05,
        error_for_minutes: int = 5,
        tool: str = "execute_in_sandbox",
        tool_rate_per_min: float = 60.0,
        uptime_floor_s: int = 30,
        extra_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """A Prometheus `groups:` doc scoped to one Mimir tenant, with
    tenant + project labels propagated into every rule."""
    tenant = tenant or _tenant_for(project)
    common_labels: Dict[str, str] = {
        "source": "charter",
        "project_id": project,
        "tenant": tenant,
        **(extra_labels or {}),
    }

    def _rule(name: str, expr: str, for_s: str, severity: str,
              summary: str, description: str,
              runbook: str = "") -> Dict[str, Any]:
        rule: Dict[str, Any] = {
            "alert": name,
            "expr": expr,
            "for": for_s,
            "labels": {**common_labels, "severity": severity},
            "annotations": {"summary": summary, "description": description},
        }
        if runbook:
            rule["annotations"]["runbook"] = runbook
        return rule

    rules = [
        _rule(
            "CharterHighErrorRate",
            (f'sum by (project_id) (increase(charter_error_spans_total'
             f'{{project_id="{project}",tenant="{tenant}"}}[{error_for_minutes}m])) '
             f'/ sum by (project_id) (increase(charter_spans_total'
             f'{{project_id="{project}",tenant="{tenant}"}}[{error_for_minutes}m])) '
             f'> {error_ratio}'),
            f"{error_for_minutes}m",
            "warning",
            f"High error ratio for {project} (>{error_ratio:.0%})",
            "charter_error_spans_total / charter_spans_total above threshold."),
        _rule(
            "CharterToolCallBurst",
            (f'sum by (tool) (increase(charter_tool_calls_total'
             f'{{tool="{tool}",tenant="{tenant}"}}[1m])) > {tool_rate_per_min}'),
            "2m",
            "warning",
            f"Burst of {tool} calls (>{tool_rate_per_min:.0f}/min)",
            "charter_tool_calls_total for a tool exceeded the per-minute limit."),
        _rule(
            "CharterLowUptime",
            f'charter_uptime_seconds{{tenant="{tenant}"}} < {uptime_floor_s}',
            "1m",
            "critical",
            f"{project} uptime below floor",
            "charter_uptime_seconds below the floor - agent down or restarting."),
    ]
    return {
        "groups": [{
            "name": f"charter-slo-{tenant}",
            "interval": "30s",
            "rules": rules,
        }],
    }


def label_propagation_config(
        tenant: str,
        extra_labels: Optional[Dict[str, str]] = None,
        prefix: str = "charter") -> Dict[str, Any]:
    """Mimir distributor label-propagation config for one tenant.

    Mimir propagates labels selected by `per_tenant_override` so every
    ingested time series carries the tenant + project + service labels.
    Returns the `metrics.global.label_propagation` shape.
    """
    default = {
        "source_labels": ["tenant", "project_id", "service_name"],
        "labels": ["tenant", "project_id", "service_name",
                    f"charter_tenant"],
    }
    labels = ["tenant", "project_id", "service_name", f"{prefix}_tenant"]
    for k, v in (extra_labels or {}).items():
        labels.append(k)
    out: Dict[str, Any] = {
        "enabled": True,
        "per_tenant_override": {
            tenant: {"labels": labels},
        },
    }
    return out


def mimir_provisioning_bundle(
        projects: List[str],
        prefix: str = "charter",
        error_ratio: float = 0.05,
        extra_labels: Optional[Dict[str, str]] = None,
        grafana_url: str = "http://grafana:3000",
        mimir_url: str = "http://mimir:9009",
        loki_url: str = "http://loki:3100",
        tempo_url: str = "http://tempo:3200",
        ) -> Dict[str, Any]:
    """tool: mimir_provisioning_bundle - one-shot Mimir multi-tenant
    provisioning (tenants + per-tenant rules + label propagation + Grafana
    data sources).

    Returns:
        tenants         {project: tenant_user}
        rules           {tenant_user: groups-doc}
        label_prop      {tenant_user: propagation-config}
        datasources     Grafana Mimir / Loki / Tempo / Prom data sources
    All values are JSON-serializable (a YAML subset) ready to drop into
    Grafana / Mimir provisioning.
    """
    tenants = mimir_tenants(projects, prefix=prefix)
    rules: Dict[str, Dict[str, Any]] = {}
    label_prop: Dict[str, Dict[str, Any]] = {}
    for project, tenant in tenants.items():
        rules[tenant] = tenant_rules(
            project, tenant=tenant, error_ratio=error_ratio,
            extra_labels=extra_labels)
        label_prop[tenant] = label_propagation_config(tenant,
                                                      extra_labels,
                                                      prefix=prefix)

    datasources = {
        "apiVersion": 1,
        "datasources": [
            {"name": "Charter Mimir", "type": "prometheus",
             "url": mimir_url, "access": "proxy",
             "isDefault": True,
             "jsonData": {"prometheusType": "remote"},
             "editable": True},
            {"name": "Charter Loki", "type": "loki",
             "url": loki_url, "access": "proxy"},
            {"name": "Charter Tempo", "type": "tempo",
             "url": tempo_url, "access": "proxy",
             "jsonData": {"tracesToLogs": True}},
            {"name": "Charter Grafana", "type": "grafana",
             "url": grafana_url, "access": "proxy"},
        ],
    }

    return {
        "tenants": tenants,
        "rules": rules,
        "label_propagation": label_prop,
        "datasources": datasources,
    }
