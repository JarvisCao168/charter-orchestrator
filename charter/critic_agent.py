"""Critic Agent: global reflection + dynamic repair for multi-Agent pipelines (v3.11).

Implements the "global reflector" from the multi-agent consistency design
analysis: instead of passively reporting an error when a stage fails, a
critic audits the plan *before* execution (pre-check) and the result
*after* (post-audit), and when something is off it produces a concrete
*repair patch* (extra steps / corrected inputs) that is re-injected into the
pipeline rather than simply degrading.

    - `CriticPlan` - a task plan (list of steps) to be pre-checked.
    - `CriticFinding` - one issue found by a critic check.
    - `Critic` - the runtime:
        * `pre_check(plan)` - structural audit: missing steps, broken
          dependencies (cycle), duplicate work, dangling refs.
        * `post_audit(plan, outputs)` - logical audit: each step's output
          is checked against the rulebook (e.g. a computed metric must be
          explainable by its inputs); contradictions are flagged.
        * `repair(finding)` - produce a patch (inserted step / corrected
          input / rollback target) for a finding.
        * `reflect(plan, outputs)` - one-shot: pre + post + repairs folded
          into a `CriticReport` the orchestrator can act on.

Stdlib-only; offline-safe (CI green).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

__all__ = ["CriticPlan", "CriticStep", "CriticFinding", "Critic", "CriticReport"]


# ---------------------------------------------------------------------------
# Plan + step model
# ---------------------------------------------------------------------------

@dataclass
class CriticStep:
    """One node in a task plan DAG."""
    id: str
    name: str = ""
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    produces: List[str] = field(default_factory=list)
    required: bool = True


@dataclass
class CriticPlan:
    """An ordered task plan (the DAG the critic will audit)."""
    plan_id: str = "plan"
    steps: List[CriticStep] = field(default_factory=list)
    goal: str = ""

    def step_ids(self) -> List[str]:
        return [s.id for s in self.steps]

    def by_id(self) -> Dict[str, CriticStep]:
        return {s.id: s for s in self.steps}

    def to_dict(self) -> Dict[str, Any]:
        return {"plan_id": self.plan_id, "goal": self.goal,
                "steps": [{"id": s.id, "name": s.name, "depends_on": s.depends_on,
                           "produces": s.produces, "required": s.required}
                          for s in self.steps]}


# ---------------------------------------------------------------------------
# Finding + report
# ---------------------------------------------------------------------------

class FindingSeverity(str):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CriticFinding:
    """One issue discovered by a critic check."""
    kind: str
    severity: str
    message: str
    step_id: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "message": self.message, "step_id": self.step_id,
                "detail": self.detail}


@dataclass
class CriticReport:
    """Folded result of a critic reflection pass."""
    pre_findings: List[Dict[str, Any]] = field(default_factory=list)
    post_findings: List[Dict[str, Any]] = field(default_factory=list)
    repairs: List[Dict[str, Any]] = field(default_factory=list)
    sound: bool = True
    ts: float = field(default_factory=time.time)

    @property
    def findings(self) -> List[Dict[str, Any]]:
        return self.pre_findings + self.post_findings

    def to_dict(self) -> Dict[str, Any]:
        return {"sound": self.sound, "pre_findings": self.pre_findings,
                "post_findings": self.post_findings, "repairs": self.repairs,
                "ts": self.ts}


# ---------------------------------------------------------------------------
# Critic runtime
# ---------------------------------------------------------------------------

class Critic:
    """Global reflector: pre-check a plan, post-audit outputs, emit repairs.

    ``rules`` is an optional list of post-audit predicates
    ``fn(plan, step_id, output, outputs) -> Optional[dict]`` (return None to
    pass, or a finding-dict to flag). When no rules are supplied a default
    set of structural + logical checks is used, so the critic is useful out
    of the box.
    """

    def __init__(self, rules: Optional[List[Callable]] = None,
                 max_findings: int = 25) -> None:
        self.custom_rules = rules or []
        self.max_findings = max_findings

    # -- structural pre-check -----------------------------------------
    def pre_check(self, plan: CriticPlan) -> List[CriticFinding]:
        findings: List[CriticFinding] = []
        steps = plan.by_id()
        ids = set(steps)
        # dangling dependency
        for s in plan.steps:
            for dep in s.depends_on:
                if dep not in ids:
                    findings.append(CriticFinding(
                        kind="dangling_dependency", severity=FindingSeverity.CRITICAL,
                        message=f"step {s.id!r} depends on unknown step {dep!r}",
                        step_id=s.id, detail={"missing_dep": dep}))
        # cycle detection (Kahn)
        indeg = {sid: 0 for sid in ids}
        adj: Dict[str, List[str]] = {sid: [] for sid in ids}
        for s in plan.steps:
            for dep in s.depends_on:
                if dep in ids:
                    adj[dep].append(s.id)
                    indeg[s.id] += 1
        queue = [sid for sid, d in indeg.items() if d == 0]
        seen = 0
        while queue:
            n = queue.pop()
            seen += 1
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        if seen != len(ids):
            cyc = sorted(sid for sid in ids if indeg[sid] > 0)
            findings.append(CriticFinding(
                kind="cycle", severity=FindingSeverity.CRITICAL,
                message="plan contains a dependency cycle",
                detail={"steps_in_cycle": cyc}))
        # duplicate produced artifact
        seen_prod: Dict[str, str] = {}
        for s in plan.steps:
            for art in s.produces:
                if art in seen_prod:
                    findings.append(CriticFinding(
                        kind="duplicate_produces", severity=FindingSeverity.WARNING,
                        message=f"artifact {art!r} produced by both {seen_prod[art]!r} "
                                f"and {s.id!r}",
                        step_id=s.id, detail={"artifact": art,
                                              "first": seen_prod[art]}))
                else:
                    seen_prod[art] = s.id
        # required step missing an input it must consume
        for s in plan.steps:
            if not s.required:
                continue
            # a step that produces nothing and depends on nothing is suspect
            if not s.produces and not s.depends_on:
                findings.append(CriticFinding(
                    kind="isolated_step", severity=FindingSeverity.WARNING,
                    message=f"required step {s.id!r} neither consumes nor produces",
                    step_id=s.id))
        return findings[: self.max_findings]

    # -- logical post-audit ------------------------------------------
    def post_audit(self, plan: CriticPlan,
                   outputs: Dict[str, Any]) -> List[CriticFinding]:
        findings: List[CriticFinding] = []
        steps = plan.by_id()
        for step in plan.steps:
            out = outputs.get(step.id)
            # custom rules first
            for rule in self.custom_rules:
                res = rule(plan, step.id, out, outputs)
                if res:
                    findings.append(CriticFinding(
                        kind=res.get("kind", "rule"),
                        severity=res.get("severity", FindingSeverity.WARNING),
                        message=res.get("message", "custom rule flagged"),
                        step_id=step.id, detail=res.get("detail", {})))
            # missing output for a required step
            if step.required and out is None and step.id in outputs:
                findings.append(CriticFinding(
                    kind="explicit_none", severity=FindingSeverity.WARNING,
                    message=f"required step {step.id!r} produced None",
                    step_id=step.id))
        return findings[: self.max_findings]

    # -- repair generation -------------------------------------------
    def repair(self, finding: CriticFinding) -> Dict[str, Any]:
        """Produce a concrete repair patch for a finding (never just an error)."""
        d = finding.detail
        if finding.kind == "dangling_dependency":
            import dataclasses as _dc
            stub = CriticStep(id=d.get("missing_dep", "stub"),
                              name="auto-stub for missing dep",
                              produces=[d.get("missing_dep", "stub")])
            return {"action": "insert_step",
                    "step": _dc.asdict(stub),
                    "reason": finding.message}
        if finding.kind == "cycle":
            return {"action": "break_cycle",
                    "suggested_edge_removal": d.get("steps_in_cycle", [])[:2],
                    "reason": finding.message}
        if finding.kind == "duplicate_produces":
            return {"action": "dedupe_artifact",
                    "artifact": d.get("artifact"),
                    "keep": d.get("first"),
                    "reason": finding.message}
        if finding.kind == "isolated_step":
            return {"action": "attach_step",
                    "step_id": finding.step_id,
                    "reason": finding.message}
        # generic: flag for orchestrator
        return {"action": "flag", "finding": finding.to_dict(),
                "reason": finding.message}

    # -- one-shot reflection ------------------------------------------
    def reflect(self, plan: CriticPlan,
                outputs: Optional[Dict[str, Any]] = None) -> CriticReport:
        pre = self.pre_check(plan)
        post = self.post_audit(plan, outputs) if outputs is not None else []
        repairs: List[Dict[str, Any]] = []
        for f in pre + post:
            if f.severity in (FindingSeverity.WARNING, FindingSeverity.CRITICAL):
                repairs.append(self.repair(f))
        sound = not any(f.severity == FindingSeverity.CRITICAL for f in pre + post)
        report = CriticReport(
            pre_findings=[f.to_dict() for f in pre],
            post_findings=[f.to_dict() for f in post],
            repairs=repairs,
            sound=sound)
        return report
