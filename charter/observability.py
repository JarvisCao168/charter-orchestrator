"""Observability layer: full-chain trace + query (LangGraph/LangSmith inspired).

Emits OpenTelemetry-compatible span records so the v2.0 upgrade to Grafana
is a drop-in. Records every tool call, gate result, and checkpoint.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Span:
    span_id: str
    parent_id: Optional[str]
    name: str
    start_ts: float
    end_ts: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"

    def to_otel(self) -> Dict[str, Any]:
        """Serialize to an OpenTelemetry-semantic span dict."""
        return {
            "traceId": self.parent_id or "0" * 32,
            "spanId": self.span_id,
            "parentSpanId": self.parent_id,
            "name": self.name,
            "startTimeUnixNano": int(self.start_ts * 1e9),
            "endTimeUnixNano": int((self.end_ts or self.start_ts) * 1e9),
            "status": {"code": "OK" if self.status == "ok" else "ERROR"},
            "attributes": {f"charter.{k}": v for k, v in self.attributes.items()},
        }


class TraceLogger:
    """Per-project span logger. Bounded to avoid unbounded memory growth."""

    def __init__(self, max_spans: int = 500) -> None:
        self.max_spans = max_spans
        self.spans: List[Span] = []

    def log(self, name: str, attributes: Optional[Dict[str, Any]] = None,
            parent_id: Optional[str] = None) -> Span:
        span = Span(
            span_id=uuid.uuid4().hex[:16],
            parent_id=parent_id or (self.spans[-1].span_id if self.spans else None),
            name=name,
            start_ts=time.time(),
            attributes=attributes or {},
        )
        self.spans.append(span)
        if len(self.spans) > self.max_spans:
            self.spans = self.spans[-self.max_spans:]
        return span

    def summary(self) -> Dict[str, Any]:
        if not self.spans:
            return {"spans": 0, "duration_s": 0.0, "by_name": {}}
        by_name: Dict[str, int] = {}
        for s in self.spans:
            by_name[s.name] = by_name.get(s.name, 0) + 1
        return {
            "spans": len(self.spans),
            "duration_s": round(self.spans[-1].start_ts - self.spans[0].start_ts, 3),
            "by_name": by_name,
        }


def trace_operation(name: str, attributes: Optional[Dict[str, Any]] = None) -> Span:
    """tool 19/20 - trace_operation. Standalone span for ad-hoc instrumentation."""
    return TraceLogger().log(name, attributes)


def query_trace(trace_id: Optional[str] = None,
                spans: Optional[List[Span]] = None) -> Dict[str, Any]:
    """tool 20/20 - query_trace. Aggregate spans into a human-readable digest."""
    spans = spans or []
    if not spans:
        return {"trace_id": trace_id, "spans": 0, "note": "no spans supplied"}
    errors = [s.name for s in spans if s.status != "ok"]
    return {
        "trace_id": trace_id,
        "spans": len(spans),
        "errors": errors,
        "duration_s": round(spans[-1].start_ts - spans[0].start_ts, 3),
    }
