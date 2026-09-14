"""Real Grafana data source + dashboard provisioning (v2.1).

Goes further than `otel_export.GrafanaDashboard()` (which just emitted a
dashboard JSON): this module provisions an **actual Prometheus data source**
and wires the charter_* metrics into it, plus an OTLP->Tempo pipeline, so a
Grafana stack can ingest a live charter deployment.

Stdlib-only; all outputs are JSON/YAML ready to `grafana-cli` import or drop
into `/etc/grafana/provisioning/`.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from .otel_export import GrafanaDashboard, prometheus_text, to_otlp_json
from .observability import TraceLogger


def prometheus_data_source(name: str = "Charter",
                          url: str = "http://prometheus:9090") -> Dict[str, Any]:
    """Grafana provisioning data source for the charter Prometheus metrics."""
    return {
        "apiVersion": 1,
        "datasources": [{
            "name": name,
            "type": "prometheus",
            "access": "proxy",
            "url": url,
            "isDefault": False,
            "editable": True,
            "jsonData": {"timeInterval": "15s"},
        }],
    }


def tempo_data_source(name: str = "Charter Tempo",
                      url: str = "http://tempo:3200") -> Dict[str, Any]:
    """OTLP->Grafana Tempo data source for the charter trace spans."""
    return {
        "apiVersion": 1,
        "datasources": [{
            "name": name,
            "type": "tempo",
            "access": "proxy",
            "url": url,
            "jsonData": {"tracesToLogsVoyagerEnabled": True},
        }],
    }


def dashboard_json(project_id: str = "charter",
                   ds_prom: str = "Charter",
                   ds_tempo: str = "Charter Tempo") -> Dict[str, Any]:
    """Full dashboard: tool-call rates, error rate, uptime + a Tempo traces panel."""
    dash = GrafanaDashboard()
    dash["panels"].append({
        "type": "traces", "title": "Traces (Tempo)",
        "targets": [{"query": "{}", "datasource": ds_tempo}],
    })
    for p in dash["panels"]:
        for t in p.get("targets", []):
            t.setdefault("datasource", ds_prom)
    dash["time"] = {"from": "now-1h", "to": "now"}
    dash["refresh"] = "15s"
    dash["tags"] = ["charter", project_id]
    return dash


def prometheus_scrape_config(service: str = "charter-orchestrator",
                             port: int = 9105) -> Dict[str, Any]:
    """Prometheus scrape config so the charter `/metrics` endpoint is collected."""
    return {
        "scrape_configs": [{
            "job": "charter",
            "metrics_path": "/metrics",
            "static_configs": [{
                "targets": [f"{service}:{port}"],
                "labels": {"app": "charter-orchestrator"},
            }],
        }]
    }


def otlp_exporter_config(otlp_endpoint: str = "http://otel-collector:4318",
                         service: str = "charter-orchestrator") -> Dict[str, Any]:
    """OTLP/HTTP collector target for `to_otlp_json` batches in a live deployment."""
    return {"otlp_endpoint": otlp_endpoint, "service": service,
            "protocol": "http/protobuf"}


def live_metrics_demo(trace: Optional[TraceLogger] = None) -> Dict[str, Any]:
    """End-to-end provisioning bundle: data sources + dashboard + scrape config."""
    trace = trace or TraceLogger()
    for name in ["init_project", "advance_stage", "confirm_gate",
                 "execute_in_sandbox", "execute_in_sandbox", "confirm_gate"]:
        trace.log(name)
    return {
        "prometheus_ds": prometheus_data_source(),
        "tempo_ds": tempo_data_source(),
        "dashboard": dashboard_json(),
        "prometheus_scrape": prometheus_scrape_config(),
        "otlp_exporter": otlp_exporter_config(),
        "current_prometheus_text": prometheus_text(trace.spans),
    }
