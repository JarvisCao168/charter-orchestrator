"""OpenTelemetry export + Grafana/Prometheus metrics (v2.0).

Lifts the v1.1 in-memory TraceLogger to a production observability surface:

- `to_otlp_json(spans)` - serialize spans to an OpenTelemetry Proto-JSON batch
  (drop-in for OTLP/HTTP collectors, Jaeger, or Grafana Tempo).
- `prometheus_text(metrics)` - emit Prometheus exposition format for
  `charter_*` gauges/counters that Grafana scrapes.
- `GrafanaDashboard` - a minimal Grafana dashboard JSON template wired to the
  metrics above, ready to import into Grafana.

All stdlib; no `opentelemetry-sdk` import required. In a real deployment,
replace the serializer with the official SDK exporter - the span shape is
OTel-semantic so migration is a one-liner.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional

from .observability import Span


# ---------------------------------------------------------------------------
# OTLP/JSON export
# ---------------------------------------------------------------------------
def to_otlp_json(spans: Iterable[Span],
                 service_name: str = "charter-orchestrator") -> Dict[str, Any]:
    """Serialize spans to an OTLP/JSON `resourceSpans` batch."""
    resource_spans = [{
        "resource": {
            "attributes": [
                {"key": "service.name", "value": {"stringValue": service_name}},
                {"key": "service.version", "value": {"stringValue": "v2.0"}},
            ]
        },
        "scopeSpans": [{
            "scope": {"name": "charter", "version": "2.0.0"},
            "spans": [s.to_otel() for s in spans],
        }],
    }]
    return {"resourceSpans": resource_spans}


# ---------------------------------------------------------------------------
# Prometheus / Grafana
# ---------------------------------------------------------------------------
def _derive_metrics(spans: Iterable[Span]) -> Dict[str, float]:
    spans = list(spans)
    by_tool: Dict[str, int] = {}
    errors = 0
    for s in spans:
        by_tool[s.name] = by_tool.get(s.name, 0) + 1
        if s.status != "ok":
            errors += 1
    now = time.time()
    m: Dict[str, float] = {
        "charter_spans_total": float(len(spans)),
        "charter_error_spans_total": float(errors),
        "charter_uptime_seconds": now,
    }
    for name, cnt in by_tool.items():
        safe = name.replace("-", "_")
        m[f"charter_tool_calls_total{safe}"] = float(cnt)
    return m


def prometheus_text(spans: Iterable[Span],
                    project_id: Optional[str] = None) -> str:
    """Prometheus exposition format for a live scrape endpoint."""
    m = _derive_metrics(spans)
    labels = f'project_id="{project_id or "default"}"'
    lines = [
        "# HELP charter_spans_total Total governance spans recorded",
        f"# TYPE charter_spans_total counter",
        f"charter_spans_total{{{labels}}} {m['charter_spans_total']:.0f}",
        "# HELP charter_error_spans_total Spans with status=error",
        f"charter_error_spans_total{{{labels}}} {m['charter_error_spans_total']:.0f}",
    ]
    for k, v in m.items():
        if k.startswith("charter_tool_calls_total"):
            tool = k.replace("charter_tool_calls_total", "").lstrip("{")
            lines += [
                f"# HELP charter_tool_calls_total Calls per tool",
                f"charter_tool_calls_total{{tool=\"{tool}\"}} {v:.0f}",
            ]
    return "\n".join(lines) + "\n"


def GrafanaDashboard() -> Dict[str, Any]:
    """A minimal Grafana dashboard JSON wired to the charter_* metrics.

    Import via Grafana -> Dashboards -> Import -> paste this JSON.
    """
    return {
        "title": "Charter Orchestrator",
        "schemaVersion": 39,
        "panels": [
            {"type": "timeseries", "title": "Tool calls", "targets": [
                {"expr": "sum by (tool) (charter_tool_calls_total)"}]},
            {"type": "stat", "title": "Total spans", "targets": [
                {"expr": "charter_spans_total"}]},
            {"type": "stat", "title": "Error rate", "targets": [
                {"expr": "charter_error_spans_total / charter_spans_total"}]},
        ],
        "annotations": {"list": []},
    }


# ---------------------------------------------------------------------------
# High-level: export a project's TraceLogger
# ---------------------------------------------------------------------------
def export_project(trace, project_id: Optional[str] = None,
                   fmt: str = "otlp") -> Dict[str, Any] | str:
    """`fmt` in {otlp, prometheus, grafana}."""
    if fmt == "otlp":
        return to_otlp_json(trace.spans)
    if fmt == "prometheus":
        return prometheus_text(trace.spans, project_id)
    if fmt == "grafana":
        return GrafanaDashboard()
    raise ValueError(f"unknown export format {fmt!r}")
