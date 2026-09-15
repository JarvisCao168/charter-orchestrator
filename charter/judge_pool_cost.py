"""Multi-trigger + cost-aware autoscaling for the distributed judge pool
(v2.9).

Lifts `charter/judge_pool_live.py` (single pending-task trigger + a CPU HPA
fallback) to a **multi-trigger, cost-aware** autoscaler:

    - `JudgePoolAutoscaler` - plans a KEDA ScaledObject with *N* triggers
      (pending-task queue, Prometheus rule breach, a calendar/workload
      window, and a burst heuristic), plus a **cost ceiling** that caps
      maxReplicas so the pool can't run away:
        * `max_replicas_for_budget(budget, per_replica_cost, min_r, max_r)`
          computes the largest replica count that fits a $ budget.
        * `cost_estimate(replicas, duration_min, per_replica_cost)` ->
          projected spend.
        * `scale_decision(metrics, budget)` -> a recommended replica count
          that respects the triggers *and* the cost ceiling.
    - `render_cost_autoscaler(pool, ...)` - one-shot: the KEDA doc + a
      cost-ceiling metadata block + a scaling-decision table, all JSON.

The cost model is deliberately simple: a flat per-replica-hour rate (the
K8s Job runs a small GPU/CPU container; the operator sets the rate). The
module emits the *planning* artifacts; the actual spend happens in the
cloud. Stdlib-only.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .judge_pool import JudgePoolPlan
from .judge_pool_live import autoscaler_plan

__all__ = [
    "JudgePoolAutoscaler", "render_cost_autoscaler",
]

# built-in trigger kinds
_TRIGGERS = ("pending-judge-tasks", "prometheus", "calendar", "burst")


@dataclass
class JudgePoolAutoscaler:
    """Multi-trigger + cost-aware autoscaler for a judge pool."""
    plan: JudgePoolPlan
    min_replicas: int = 1
    max_replicas: int = 24
    # cost model
    per_replica_hour: float = 0.35     # $/replica/hour (operator-tunable)
    daily_budget: float = 50.0         # hard $ cap per day
    # trigger thresholds
    pending_threshold: int = 24
    burst_threshold: int = 64
    prometheus_rule: str = ""           # e.g. "charter_high_error_rate"
    calendar_window: str = ""           # e.g. "09:00-18:00" (work hours)

    # -- cost math --------------------------------------------------------
    def max_replicas_for_budget(self,
                                budget: Optional[float] = None,
                                duration_min: int = 60,
                                min_r: Optional[int] = None,
                                max_r: Optional[int] = None
                                ) -> int:
        """The largest replica count that fits `budget` over
        `duration_min` at the per-replica rate. Clamped to
        [min_replicas, max_replicas]."""
        budget = budget if budget is not None else self.daily_budget
        duration_min = max(1, duration_min)
        per_replica_cost = self.per_replica_hour * (duration_min / 60.0)
        if per_replica_cost <= 0:
            return max_r or self.max_replicas
        cap = int(math.floor(budget / per_replica_cost))
        lo = min_r if min_r is not None else self.min_replicas
        hi = max_r if max_r is not None else self.max_replicas
        return max(lo, min(hi, cap, hi))

    def cost_estimate(self, replicas: int, duration_min: int) -> float:
        """Projected $ spend for `replicas` running `duration_min`."""
        return round(replicas * self.per_replica_hour
                     * (max(1, duration_min) / 60.0), 4)

    def scale_decision(self, metrics: Dict[str, Any],
                       budget: Optional[float] = None,
                       duration_min: int = 60) -> Dict[str, Any]:
        """Recommend a replica count from the triggers, capped by the cost
        budget. `metrics` carries {pending_tasks, burst, calendar_active,
        prometheus_breach}. The recommendation is the max of the per-trigger
        asks, clamped to the cost ceiling."""
        asks: List[Dict[str, Any]] = []
        pending = int(metrics.get("pending_tasks", 0))
        if pending >= self.pending_threshold:
            # one extra replica per 12 pending tasks above the threshold
            need = 1 + max(0, (pending - self.pending_threshold) // 12)
            asks.append({"trigger": "pending-judge-tasks", "ask": need})
        burst = int(metrics.get("burst", 0))
        if burst >= self.burst_threshold:
            asks.append({"trigger": "burst",
                          "ask": 1 + (burst // self.burst_threshold)})
        if metrics.get("calendar_active") and self.calendar_window:
            asks.append({"trigger": "calendar", "ask": 2})
        if metrics.get("prometheus_breach") and self.prometheus_rule:
            asks.append({"trigger": "prometheus", "ask": 2})

        if not asks:
            recommended = self.min_replicas
        else:
            recommended = max(a["ask"] for a in asks)

        ceiling = self.max_replicas_for_budget(budget=budget,
                                               duration_min=duration_min)
        capped = min(recommended, ceiling, self.max_replicas)
        return {
            "recommended_replicas": capped,
            "raw_ask": recommended,
            "cost_ceiling": ceiling,
            "budget": budget if budget is not None else self.daily_budget,
            "estimated_cost": self.cost_estimate(capped, duration_min),
            "triggers": asks,
            "cost_limited": recommended > ceiling,
        }

    # -- plan -------------------------------------------------------------
    def keda_doc(self, triggers: Optional[List[str]] = None,
                 namespace: str = "charter"
                 ) -> Dict[str, Any]:
        """A KEDA ScaledObject with *multiple* triggers + a cost-ceiling
        metadata block."""
        triggers = [t for t in (triggers or []) if t in _TRIGGERS] or \
            ["pending-judge-tasks"]
        trig_docs: List[Dict[str, Any]] = []
        for t in triggers:
            if t == "pending-judge-tasks":
                trig_docs.append({
                    "type": "externals",
                    "metadata": {"metricName": "pending-judge-tasks",
                                 "threshold": str(self.pending_threshold)},
                })
            elif t == "prometheus" and self.prometheus_rule:
                trig_docs.append({
                    "type": "prometheus",
                    "metadata": {"server": "http://prometheus:9090",
                                  "query": f"{self.prometheus_rule} == 1",
                                  "threshold": "2"},
                })
            elif t == "calendar" and self.calendar_window:
                trig_docs.append({
                    "type": "calendar",
                    "metadata": {"schedule": self.calendar_window,
                                  "timezone": "UTC"},
                })
            elif t == "burst":
                trig_docs.append({
                    "type": "externals",
                    "metadata": {"metricName": "charter-judge-burst",
                                  "threshold": str(self.burst_threshold)},
                })
        ceiling = self.max_replicas_for_budget()
        return {
            "apiVersion": "keda.sh/v1alpha1",
            "kind": "ScaledObject",
            "metadata": {"name": f"charter-judge-{self.plan.pool_id}",
                          "namespace": namespace,
                          "labels": {"charter.io/pool": self.plan.pool_id,
                                     "charter.io/role": "autoscaler",
                                     "charter.io/cost-aware": "true"}},
            "spec": {
                "scaleTargetRef": {
                    "name": f"charter-judge-{self.plan.pool_id}-jobs"},
                "minReplicaCount": self.min_replicas,
                "maxReplicaCount": ceiling,
                "pollingInterval": 30,
                "triggers": trig_docs,
                "triggers_note": "multi-trigger: any one firing scales the "
                                 "pool; max is cost-capped",
                "cost_ceiling": {
                    "per_replica_hour": self.per_replica_hour,
                    "daily_budget": self.daily_budget,
                    "max_replicas_for_budget": ceiling,
                },
            },
        }


def render_cost_autoscaler(
        plan: JudgePoolPlan,
        min_replicas: int = 1,
        max_replicas: int = 24,
        per_replica_hour: float = 0.35,
        daily_budget: float = 50.0,
        pending_threshold: int = 24,
        burst_threshold: int = 64,
        prometheus_rule: str = "",
        calendar_window: str = "",
        triggers: Optional[List[str]] = None,
        namespace: str = "charter") -> Dict[str, str]:
    """tool: render_cost_autoscaler - one-shot multi-trigger + cost-aware
    autoscaler bundle for a judge pool.

    Returns {"keda_scaledobject","cost_ceiling","scale_table"} where
    scale_table shows the recommended replicas + cost at a few budget /
    trigger points.
    """
    asc = JudgePoolAutoscaler(
        plan=plan, min_replicas=min_replicas, max_replicas=max_replicas,
        per_replica_hour=per_replica_hour, daily_budget=daily_budget,
        pending_threshold=pending_threshold, burst_threshold=burst_threshold,
        prometheus_rule=prometheus_rule, calendar_window=calendar_window)
    keda = asc.keda_doc(triggers=triggers, namespace=namespace)

    # a small scale-decision table across budgets
    table: List[Dict[str, Any]] = []
    for budget in (10.0, daily_budget, daily_budget * 2):
        decision = asc.scale_decision(
            {"pending_tasks": pending_threshold + 24,
             "burst": burst_threshold, "calendar_active": True,
             "prometheus_breach": bool(prometheus_rule)},
            budget=budget, duration_min=60)
        table.append({
            "budget": budget,
            "recommended_replicas": decision["recommended_replicas"],
            "cost_ceiling": decision["cost_ceiling"],
            "estimated_cost": decision["estimated_cost"],
            "cost_limited": decision["cost_limited"],
            "triggers_firing": [t["trigger"] for t in decision["triggers"]],
        })
    return {
        "keda_scaledobject": json.dumps(keda, indent=2),
        "cost_ceiling": json.dumps(
            {"per_replica_hour": asc.per_replica_hour,
             "daily_budget": asc.daily_budget,
             "max_replicas": asc.max_replicas_for_budget()},
            indent=2),
        "scale_table": json.dumps(table, indent=2),
    }
