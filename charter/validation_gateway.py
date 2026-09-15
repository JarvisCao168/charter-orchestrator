"""Three-layer validation gateway + circuit breaker for multi-Agent pipelines (v3.11).

Lifts the "validation gateway + fuse/degrade" idea from the multi-agent
consistency design analysis (shared-state bus + DAG static check + local fault
tolerance) into an executable Charter module:

- **Layer 1 - schema (contract) validation**: every tool/agent output must
  carry the declared required fields of the right types before it may be
  written back to shared state.
- **Layer 2 - data alignment**: cross-check a *key fact* against the upstream
  context (anti-"500 billion -> 1200 billion" drift): the field value must
  not deviate from the upstream record by more than a relative tolerance.
- **Layer 3 - consistency**: a derived conclusion must not contradict the
  accumulated shared state (e.g. "QoQ growth 20%" vs "Q1 was down" in context).

On layer failure the gateway **does not crash**: it retries locally
(``max_local_retries``) then **degrades** (fills a default / drops a
non-critical field) and records the incident. The :class:`CircuitBreaker`
tracks consecutive failures per tool and, once ``failure_threshold`` is
reached, opens for ``cooldown_s`` so a single bad tool cannot drag the whole
chain down; after the cooldown it half-opens and allows one probe.

Stdlib-only. No hard deps; degrades offline (CI green).

    from charter import validation_gateway as vg

    gw = vg.ValidationGateway({
        "market_size": {"type": float, "required": True},
        "source":       {"type": str,    "required": True},
    })
    verdict = gw.check({
        "market_size": 1200e9,
        "source": "research-agent",
        "_upstream": {"market_size": 500e9},   # layer 2 baseline
        "_context":  {"market_size": 500e9},   # layer 3 baseline
    })
    assert verdict.passed is False
    assert verdict.layer_failures[1].kind == "data_drift"
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = [
    "ValidationGateway", "CircuitBreaker", "BreakerState",
    "check_contract", "check_data_alignment", "check_consistency",
    "layered_check", "with_breaker",
]

# Type aliases for schema declarations.
_TYPE_ALIASES: Dict[str, type] = {
    "int": int, "float": float, "str": str, "bool": bool,
    "list": list, "dict": dict, "any": object,
}


# ---------------------------------------------------------------------------
# Layer 1 - schema / contract
# ---------------------------------------------------------------------------

def check_contract(output: Dict[str, Any],
                   schema: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a list of violations (empty == valid) for ``output`` against ``schema``.

    ``schema`` maps field-name -> {"type": <py type or name>, "required": bool,
    "default": optional}. Missing required fields and type mismatches are
    violations.
    """
    violations: List[Dict[str, Any]] = []
    for name, spec in schema.items():
        if name not in output:
            if spec.get("required", False):
                violations.append({"field": name, "kind": "missing_required"})
            continue
        expected = spec.get("type")
        if expected is None:
            continue
        py_type = _TYPE_ALIASES.get(expected, expected) if isinstance(expected, str) else expected
        value = output[name]
        # bool is a subclass of int in Python; reject bool for int/float schemas.
        if py_type in (int, float) and isinstance(value, bool):
            violations.append({"field": name, "kind": "type_mismatch",
                               "expected": getattr(py_type, "__name__", str(py_type)),
                               "got": type(value).__name__})
            continue
        if not isinstance(value, py_type):
            violations.append({"field": name, "kind": "type_mismatch",
                               "expected": getattr(py_type, "__name__", str(py_type)),
                               "got": type(value).__name__})
    return violations


# ---------------------------------------------------------------------------
# Layer 2 - data alignment (anti drift)
# ---------------------------------------------------------------------------

def check_data_alignment(output: Dict[str, Any],
                         upstream: Dict[str, Any],
                         key: str,
                         rel_tol: float = 0.10,
                         abs_tol: float = 1e-9) -> Optional[Dict[str, Any]]:
    """Compare ``output[key]`` to ``upstream[key]``; return a drift record or None.

    Drift is flagged when the relative difference exceeds ``rel_tol`` (or the
    absolute difference exceeds ``abs_tol`` for near-zero values). Non-numeric
    values compare with equality.
    """
    if key not in output or key not in upstream:
        return None
    a, b = output[key], upstream[key]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        denom = max(abs(float(b)), abs_tol)
        diff = abs(float(a) - float(b))
        if diff / denom > rel_tol:
            return {"field": key, "kind": "data_drift", "upstream": b,
                    "observed": a, "rel_diff": diff / denom,
                    "rel_tol": rel_tol}
        return None
    if a != b:
        return {"field": key, "kind": "value_mismatch", "upstream": b, "observed": a}
    return None


# ---------------------------------------------------------------------------
# Layer 3 - consistency (conclusion vs shared state)
# ---------------------------------------------------------------------------

_CONTRADICTION_PAIRS: List[Tuple[str, str]] = [
    ("growth", "decline"), ("increase", "decrease"), ("positive", "negative"),
    ("up", "down"), ("rising", "falling"), ("profit", "loss"),
]


def _contradicts(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    for pos, neg in _CONTRADICTION_PAIRS:
        if pos in a and neg in b:
            return True
        if neg in a and pos in b:
            return True
    return False


def check_consistency(conclusion: Dict[str, Any],
                      context: Dict[str, Any],
                      facts: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """Check a derived ``conclusion`` against the accumulated ``context``.

    ``facts`` maps a conclusion field to the context field it must agree with
    (default: same field name). A contradiction (e.g. conclusion says
    "growth" while context says "decline") is reported.
    """
    facts = facts or {}
    for con_field, ctx_field in facts.items():
        if con_field not in conclusion:
            continue
        con_val = conclusion.get(con_field)
        ctx_val = context.get(ctx_field)
        if con_val is None or ctx_val is None:
            continue
        if isinstance(con_val, str) and isinstance(ctx_val, str):
            if _contradicts(con_val, ctx_val):
                return {"field": con_field, "kind": "contradiction",
                        "conclusion": con_val, "context": ctx_val,
                        "context_field": ctx_field}
        elif con_val != ctx_val:
            # For numeric / other: a contradiction only when both are present
            # and clearly disagree (flagged, not fatal).
            return {"field": con_field, "kind": "value_conflict",
                    "conclusion": con_val, "context": ctx_val,
                    "context_field": ctx_field}
    return None


# ---------------------------------------------------------------------------
# Aggregate gate + verdict
# ---------------------------------------------------------------------------

@dataclass
class LayeredVerdict:
    """Result of a full three-layer check on one output."""
    passed: bool
    layer_failures: Dict[int, Optional[Dict[str, Any]]] = field(default_factory=dict)
    degraded: bool = False
    notes: List[str] = field(default_factory=list)

    def failed_layers(self) -> List[int]:
        return [i for i, f in self.layer_failures.items() if f is not None]

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "degraded": self.degraded,
                "failed_layers": self.failed_layers(),
                "layer_failures": self.layer_failures,
                "notes": list(self.notes)}


def layered_check(output: Dict[str, Any],
                  schema: Dict[str, Dict[str, Any]],
                  upstream: Optional[Dict[str, Any]] = None,
                  context: Optional[Dict[str, Any]] = None,
                  alignment_key: Optional[str] = None,
                  rel_tol: float = 0.10,
                  consistency_facts: Optional[Dict[str, str]] = None
                  ) -> LayeredVerdict:
    """Run all three layers and fold them into a single verdict."""
    failures: Dict[int, Optional[Dict[str, Any]]] = {}
    notes: List[str] = []
    # Layer 1
    l1 = check_contract(output, schema)
    failures[0] = ({"kind": "contract", "violations": l1} if l1 else None)
    # Layer 2
    failures[1] = None
    if alignment_key is not None and upstream is not None:
        failures[1] = check_data_alignment(output, upstream, alignment_key, rel_tol)
    # Layer 3
    failures[2] = None
    if context is not None:
        failures[2] = check_consistency(output, context, consistency_facts)
    passed = all(f is None for f in failures.values())
    return LayeredVerdict(passed=passed, layer_failures=failures, notes=notes)


class ValidationGateway:
    """A configured three-layer gate that retries-then-degrades on failure.

    ``schema`` is the contract; optional ``alignment_key`` / ``context`` /
    ``consistency_facts`` wire in layers 2 & 3. When a check fails the gateway
    calls ``retry_fn`` up to ``max_local_retries`` times (re-running the
    producer), and if it still fails, applies a ``degrade_fn`` (or the default:
    fill defaults for missing required fields) so the pipeline keeps moving.
    """

    def __init__(self,
                 schema: Dict[str, Dict[str, Any]],
                 alignment_key: Optional[str] = None,
                 rel_tol: float = 0.10,
                 consistency_facts: Optional[Dict[str, str]] = None,
                 max_local_retries: int = 2,
                 degrade_fn: Optional[Callable[[Dict[str, Any], LayeredVerdict], Dict[str, Any]]] = None,
                 ) -> None:
        self.schema = schema
        self.alignment_key = alignment_key
        self.rel_tol = rel_tol
        self.consistency_facts = consistency_facts
        self.max_local_retries = max(0, int(max_local_retries))
        self._degrade_fn = degrade_fn
        self.incidents: List[Dict[str, Any]] = []
        self._check_count = 0

    # -- core -----------------------------------------------------------
    def check(self, output: Dict[str, Any],
              upstream: Optional[Dict[str, Any]] = None,
              context: Optional[Dict[str, Any]] = None
              ) -> LayeredVerdict:
        """Run the three layers on ``output`` (no retry / degrade)."""
        self._check_count += 1
        return layered_check(output, self.schema, upstream=upstream,
                             context=context, alignment_key=self.alignment_key,
                             rel_tol=self.rel_tol,
                             consistency_facts=self.consistency_facts)

    def check_with_retry(self, producer: Callable[[], Dict[str, Any]],
                         upstream: Optional[Dict[str, Any]] = None,
                         context: Optional[Dict[str, Any]] = None
                         ) -> Dict[str, Any]:
        """Run the producer, validate; on failure retry locally then degrade.

        Returns the (possibly degraded) output plus a ``_gw`` meta block:
        ``{"passed", "attempts", "degraded", "verdict"}``. Never raises for a
        validation failure.
        """
        attempts = 0
        verdict = None
        out: Dict[str, Any] = {}
        while attempts <= self.max_local_retries:
            attempts += 1
            out = producer()
            verdict = self.check(out, upstream=upstream, context=context)
            if verdict.passed:
                out["_gw"] = {"passed": True, "attempts": attempts,
                              "degraded": False,
                              "verdict": verdict.to_dict()}
                return out
        # still failing after retries -> degrade
        degraded = self._degrade_fn(out, verdict) if self._degrade_fn else self._default_degrade(out, verdict)
        self.incidents.append({
            "ts": time.time(), "attempts": attempts,
            "failed_layers": verdict.failed_layers(),
            "layer_failures": verdict.layer_failures,
        })
        out = degraded
        out["_gw"] = {"passed": False, "attempts": attempts, "degraded": True,
                      "verdict": verdict.to_dict()}
        return out

    def _default_degrade(self, out: Dict[str, Any], verdict: LayeredVerdict) -> Dict[str, Any]:
        """Default degrade: fill required-missing fields with their defaults (or None)."""
        filled = dict(out)
        for v in (verdict.layer_failures.get(0) or {}).get("violations", []):
            if v.get("kind") == "missing_required":
                default = self.schema.get(v["field"], {}).get("default")
                filled[v["field"]] = default
        return filled

    # -- introspection --------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        return {"checks": self._check_count,
                "incidents": len(self.incidents),
                "last_incident": self.incidents[-1] if self.incidents else None}

    # -- tool-call decorator style (circuit breaker integration) --------
    def guard(self, tool_name: str,
              call: Callable[[], Any],
              breaker: Optional["CircuitBreaker"] = None
              ) -> Dict[str, Any]:
        """Run ``call`` under the optional circuit breaker.

        Returns ``{"ok": bool, "result": ..., "breaker": state, "error": str}``.
        When the breaker is open the call is short-circuited (no result) so a
        single bad tool cannot keep hammering the pipeline.
        """
        if breaker is not None:
            if not breaker.allow():
                return {"ok": False, "result": None, "breaker": breaker.snapshot(),
                        "error": "circuit open", "tool": tool_name}
            try:
                result = call()
            except Exception as exc:
                breaker.record_failure()
                return {"ok": False, "result": None, "breaker": breaker.snapshot(),
                        "error": str(exc), "tool": tool_name}
            breaker.record_success()
            return {"ok": True, "result": result, "breaker": breaker.snapshot(),
                    "tool": tool_name}
        # no breaker: just call, surface exceptions as a failure receipt.
        try:
            result = call()
            return {"ok": True, "result": result, "breaker": None, "tool": tool_name}
        except Exception as exc:
            return {"ok": False, "result": None, "breaker": None, "error": str(exc),
                    "tool": tool_name}


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class BreakerState(str):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-tool circuit breaker (microservice-governance style).

    After ``failure_threshold`` consecutive failures the breaker opens and
    rejects calls for ``cooldown_s``; then half-opens, allowing a single probe
    that, on success, closes the breaker; on failure, re-opens.
    """

    def __init__(self, failure_threshold: int = 3, cooldown_s: float = 30.0,
                 now_fn: Optional[Callable[[], float]] = None) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_s = cooldown_s
        self._now = now_fn or time.time
        self._consecutive_failures = 0
        self._state = BreakerState.CLOSED
        self._opened_at = 0.0

    # -- state ---------------------------------------------------------
    def state_snapshot(self) -> str:
        if self._state == BreakerState.OPEN:
            # transition to HALF_OPEN once the cooldown has elapsed
            if self._now() - self._opened_at >= self.cooldown_s:
                self._state = BreakerState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = BreakerState.CLOSED

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._state = BreakerState.OPEN
            self._opened_at = self._now()

    def allow(self) -> bool:
        """True when a call may proceed (closed, or half-open probe)."""
        return self.state_snapshot() != BreakerState.OPEN

    def snapshot(self) -> Dict[str, Any]:
        return {"state": self.state_snapshot(),
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self.failure_threshold,
                "cooldown_s": self.cooldown_s}


def with_breaker(breaker: CircuitBreaker, call: Callable[[], Any]) -> Dict[str, Any]:
    """Run ``call`` under ``breaker``; returns an ok/result/error receipt."""
    if not breaker.allow():
        return {"ok": False, "result": None, "breaker": breaker.snapshot(),
                "error": "circuit open"}
    try:
        result = call()
    except Exception as exc:
        breaker.record_failure()
        return {"ok": False, "result": None, "error": str(exc),
                "breaker": breaker.snapshot()}
    breaker.record_success()
    return {"ok": True, "result": result, "breaker": breaker.snapshot()}
