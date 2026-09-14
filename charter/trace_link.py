"""Full OTel -> Jaeger / Grafana-Trace link (v2.2).

Lifts `charter.otel_export` (OTLP/JSON batch + Prometheus text + Grafana
dashboard) into an *end-to-end trace pipeline*:

    TraceLogger -> to_otlp_json -> push_to_jaeger / push_to_tempo
                                            |
                                            v
    TraceQuery (query spans back from a Jaeger v2 / Tempo HTTP backend)
                                            |
                                            v
    aggregate_traces (per-service SLO digests: p50/p95, error rate, RPS)

Everything is stdlib. The exporters are thin HTTP POST wrappers that accept
the OTLP/JSON body already produced by `to_otlp_json`, so migration to the
official `opentelemetry-sdk` exporters is a one-line swap when the real
SDK is available.

Backends:
    - Jaeger:  collector v1 HTTP (`:14268/api/traces`)
    - Tempo:   Grafana Tempo OTLP/HTTP (`:4318`) or its query frontend
    - Jaeger v2: query API (`:16686/api/traces`) for read-back

If no backend is reachable, exporters return a *pending* payload dict so the
caller can retry or persist; nothing raises.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .observability import Span, TraceLogger, query_trace
from .otel_export import to_otlp_json

__all__ = [
    "TraceLink", "JaegerPush", "TempoPush", "JaegerQuery",
    "aggregate_traces", "slo_summary",
]


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------
class _OTLPExporter:
    def __init__(self, url: str, timeout: int = 15,
                 headers: Optional[Dict[str, str]] = None) -> None:
        self.url = url
        self.timeout = timeout
        self.headers = {
            "Content-Type": "application/json",
            **(headers or {}),
        }

    def push(self, spans: Sequence[Span],
             service_name: str = "charter-orchestrator") -> Dict[str, Any]:
        """POST an OTLP/JSON batch. Returns {sent, pending, bytes}."""
        batch = to_otlp_json(spans, service_name)
        body = json.dumps(batch).encode()
        try:
            req = urllib.request.Request(
                self.url, data=body, method="POST", headers=self.headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp.read()
            return {"sent": len(spans), "pending": 0, "bytes": len(body),
                    "http_status": resp.status}
        except Exception as exc:  # network / 4xx / 5xx -> keep payload
            return {"sent": 0, "pending": len(spans), "bytes": len(body),
                    "error": str(exc)[:200], "body": batch}


class JaegerPush(_OTLPExporter):
    """Jaeger collector v1 HTTP (all-in-one, port 14268)."""

    def __init__(self, url: Optional[str] = None,
                 token: Optional[str] = None, timeout: int = 15) -> None:
        url = url or os.environ.get(
            "JAEGER_COLLECTOR_URL", "http://localhost:14268/api/traces")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        super().__init__(url, timeout, headers)


class TempoPush(_OTLPExporter):
    """Grafana Tempo OTLP/HTTP endpoint (port 4318)."""

    def __init__(self, url: Optional[str] = None,
                 token: Optional[str] = None, timeout: int = 15) -> None:
        url = url or os.environ.get(
            "TEMPO_OTLP_URL", "http://localhost:4318/v1/traces")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        super().__init__(url, timeout, headers)


class JaegerQuery:
    """Read spans back from a Jaeger v2 / v1 HTTP query backend."""

    def __init__(self, url: Optional[str] = None,
                 token: Optional[str] = None, timeout: int = 20) -> None:
        self.url = url or os.environ.get(
            "JAEGER_QUERY_URL", "http://localhost:16686/api/traces")
        self.token = token
        self.timeout = timeout

    def fetch(self, service: str = "charter-orchestrator",
              limit: int = 100) -> List[Span]:
        target = f"{self.url.rstrip('/')}?service={service}&limit={limit}"
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(target, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        spans: List[Span] = []
        for trace in data.get("data", []):
            for sp in trace.get("spans", []):
                spans.append(Span(
                    span_id=sp.get("spanID", "0")[:16],
                    parent_id=sp.get("references") and
                    sp["references"][0].get("spanID") or None,
                    name=sp.get("operationName", sp.get("name", "span")),
                    start_ts=float(sp.get("startTime", 0)) / 1e9,
                    end_ts=float(sp.get("endTime", sp.get("startTime", 0))) / 1e9,
                    status="ok",
                    attributes={k: v.get("value", v)
                                for k, v in sp.get("tags", {}).items()},
                ))
        return spans


# ---------------------------------------------------------------------------
# Aggregation / SLO
# ---------------------------------------------------------------------------
def _pct(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, int(round(p / 100.0 * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def aggregate_traces(spans: Sequence[Span]) -> Dict[str, Any]:
    """Per-service SLO digest: span counts, p50/p95 latency, error rate."""
    spans = list(spans)
    by_service: Dict[str, List[Span]] = {}
    for s in spans:
        svc = s.attributes.get("service.name") or \
            s.attributes.get("charter.service") or "charter-orchestrator"
        by_service.setdefault(svc, []).append(s)

    services: Dict[str, Any] = {}
    for svc, ss in by_service.items():
        durations = sorted(
            max(0.0, (s.end_ts or s.start_ts) - s.start_ts) for s in ss)
        errors = sum(1 for s in ss if s.status != "ok")
        services[svc] = {
            "spans": len(ss),
            "errors": errors,
            "error_rate": round(errors / len(ss), 4) if ss else 0.0,
            "p50_ms": round(_pct(durations, 50) * 1000, 2),
            "p95_ms": round(_pct(durations, 95) * 1000, 2),
            "rps": round(len(ss) / max(1.0,
                        (ss[-1].start_ts - ss[0].start_ts)), 3) if len(ss) > 1 else 0.0,
        }
    total = len(spans)
    total_errors = sum(v["errors"] for v in services.values())
    return {
        "services": services,
        "total_spans": total,
        "total_errors": total_errors,
        "global_error_rate": round(total_errors / total, 4) if total else 0.0,
    }


def slo_summary(spans: Sequence[Span],
                s_lo_ms: float = 500.0, s_lo_error: float = 0.05) -> Dict[str, Any]:
    """Boolean SLO check: p95 latency and error rate within targets."""
    agg = aggregate_traces(spans)
    per_svc = {}
    for svc, m in agg["services"].items():
        per_svc[svc] = {
            "p95_within_slo": m["p95_ms"] <= s_lo_ms,
            "error_within_slo": m["error_rate"] <= s_lo_error,
            "met": m["p95_ms"] <= s_lo_ms and m["error_rate"] <= s_lo_error,
            "p95_ms": m["p95_ms"], "error_rate": m["error_rate"],
        }
    met = all(v["met"] for v in per_svc.values())
    return {
        "target_p95_ms": s_lo_ms, "target_error_rate": s_lo_error,
        "services": per_svc, "slo_met": met,
        "summary": "MET" if met else "BREACHED",
    }


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------
class TraceLink:
    """tool: trace_link - wire a TraceLogger to Jaeger/Tempo end-to-end.

    Usage:
        link = TraceLink("jaeger")
        sp = logger.log("tool_call", {...})
        link.export([sp])                  # push to collector
        link.slo([sp])                     # SLO digest
    """

    def __init__(self, backend: str = "jaeger",
                 push_url: Optional[str] = None,
                 query_url: Optional[str] = None,
                 token: Optional[str] = None) -> None:
        self.backend = backend
        if backend == "tempo":
            self._push = TempoPush(push_url, token)
        else:
            self._push = JaegerPush(push_url, token)
        self._query = JaegerQuery(query_url, token)

    def export(self, spans: Sequence[Span],
               service_name: str = "charter-orchestrator") -> Dict[str, Any]:
        return self._push.push(spans, service_name)

    def readback(self, service: str = "charter-orchestrator",
                 limit: int = 100) -> List[Span]:
        return self._query.fetch(service, limit)

    def digest(self, spans: Sequence[Span]) -> Dict[str, Any]:
        return aggregate_traces(spans)

    def slo(self, spans: Sequence[Span],
             p95_ms: float = 500.0, error_rate: float = 0.05) -> Dict[str, Any]:
        return slo_summary(spans, p95_ms, error_rate)
