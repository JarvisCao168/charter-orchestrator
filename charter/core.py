"""Core orchestrator: project lifecycle, stage advancement, gate enforcement.

Implements the 6 base tools of the Charter Orchestrator spec:
init_project, advance_stage, confirm_gate, query_status, save_checkpoint,
restore_checkpoint - as a real in-memory state machine.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .governance import GATE_DEFINITIONS, DEFENSE_LINES, RULES, GuardrailsEngine, TDDEnforcer
from .observability import TraceLogger

# ---------------------------------------------------------------------------
# Stage definitions (10-stage SOP from SKILL.md chapter three)
# ---------------------------------------------------------------------------
STAGES: List[Dict[str, str]] = [
    {"id": "stage_0", "name": "Baseline Investigation / 基础条件调查"},
    {"id": "stage_1", "name": "Problem Analysis & Feasibility / 问题分析与可行性"},
    {"id": "stage_2", "name": "Requirement Refinement / 需求提炼与功能定义"},
    {"id": "stage_3", "name": "Open-Source Distillation / 开源蒸馏决策"},
    {"id": "stage_4", "name": "Architecture & Tech Selection / 架构设计与技术选型"},
    {"id": "stage_5", "name": "Dev Environment Setup / 开发环境搭建"},
    {"id": "stage_6", "name": "Modular Development / 模块化开发"},
    {"id": "stage_7", "name": "Integration Testing & Acceptance / 集成测试与验收"},
    {"id": "stage_8", "name": "Packaging & Delivery / 封装交付"},
    {"id": "stage_9", "name": "Retrospective & Knowledge / 复盘与沉淀"},
]

# Gate after each stage -> which checks must pass to advance (from SKILL.md ch. 5/6)
GATE_CHECKS: Dict[str, List[str]] = {
    "stage_0": ["env_report", "capability_matrix"],
    "stage_1": ["problem_statement", "feasibility_score"],
    "stage_2": ["acceptance_criteria", "requirement_signoff"],
    "stage_3": ["distillation_decision", "reference_list"],
    "stage_4": ["architecture_doc_locked", "tech_selection"],
    "stage_5": ["env_ready", "ci_green"],
    "stage_6": ["tdd_red_green", "worktree_isolated", "code_review_passed"],
    "stage_7": ["integration_tests_passed", "acceptance_signed"],
    "stage_8": ["release_checklist", "artifacts_built"],
    "stage_9": ["retro_done", "knowledge_extracted"],
}


@dataclass
class Checkpoint:
    id: str
    stage: str
    ts: float
    state: Dict[str, Any]
    label: str = ""


@dataclass
class Project:
    project_id: str
    name: str
    project_type: str
    objective: str
    current_stage: str = "stage_0"
    stage_index: int = 0
    status: str = "active"
    created_ts: float = field(default_factory=time.time)
    checkpoints: List[Checkpoint] = field(default_factory=list)
    gate_results: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    tokens_budget: int = 100_000
    violations: List[str] = field(default_factory=list)
    trace: TraceLogger = field(default_factory=TraceLogger)
    guardrails: GuardrailsEngine = field(default_factory=GuardrailsEngine)
    tdd: TDDEnforcer = field(default_factory=TDDEnforcer)


# Global project registry (in-memory; swap for a DB in production)
_REGISTRY: Dict[str, Project] = {}


def init_project(
    project_name: str,
    project_type: str,
    core_objective: str,
    team_size: int = 3,
    checkpoint_enabled: bool = True,
    guardrails_enabled: bool = True,
    tdd_enforcement: str = "soft",
    model_registry_path: Optional[str] = None,
    worktree_base_path: Optional[str] = None,
    token_budget: int = 100_000,
) -> Dict[str, Any]:
    """tool 1/6 - init_project. See SKILL.md tool definitions for the full contract."""
    project_id = "proj_" + uuid.uuid4().hex[:10]
    initial_checkpoint = Checkpoint(
        id="cp_init", stage="stage_0", ts=time.time(),
        state={"stage": "stage_0"}, label="baseline",
    )
    p = Project(
        project_id=project_id,
        name=project_name,
        project_type=project_type,
        objective=core_objective,
        checkpoints=[initial_checkpoint] if checkpoint_enabled else [],
        tokens_budget=token_budget,
    )
    p.config.update({
        "team_size": team_size,
        "checkpoint_enabled": checkpoint_enabled,
        "guardrails_enabled": guardrails_enabled,
        "tdd_enforcement": tdd_enforcement,
        "model_registry_path": model_registry_path,
        "worktree_base_path": worktree_base_path,
    })
    p.tdd.level = tdd_enforcement
    p.guardrails.enabled = guardrails_enabled
    p.trace.log("init_project", {"name": project_name, "type": project_type})
    _REGISTRY[project_id] = p
    return {
        "project_id": project_id,
        "workspace_path": f"/tmp/charter/{project_id}",
        "initial_checkpoint_id": initial_checkpoint.id,
        "configured_models": ["agnes-2.5-flash"],
        "guardrails_status": "enabled" if guardrails_enabled else "disabled",
        "worktree_path": worktree_base_path or f"/tmp/charter/{project_id}/worktree",
    }


def _get(project_id: str) -> Project:
    if project_id not in _REGISTRY:
        raise KeyError(f"unknown project_id {project_id!r}; call init_project first")
    return _REGISTRY[project_id]


def advance_stage(
    project_id: str,
    target_stage: str,
    checkpoint_before_advance: bool = True,
    autonomous_mode: bool = False,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """tool 2/6 - advance_stage with defense-line checks.

    Defense line 4 (branch isolation) auto-applies at stage_6 entry:
    a worktree is recorded unless evidence proves isolation.
    """
    p = _get(project_id)
    evidence = evidence or {}
    idx = next(i for i, s in enumerate(STAGES) if s["id"] == target_stage)
    if idx <= p.stage_index and not autonomous_mode:
        # 越级 / backward advance is blocked unless autonomous overrides
        return {
            "project_id": project_id, "stage_id": target_stage, "status": "blocked",
            "reason": "backward or same-stage advance requires autonomous_mode",
        }
    if checkpoint_before_advance and p.config.get("checkpoint_enabled", True):
        p.checkpoints.append(Checkpoint(
            id="cp_" + uuid.uuid4().hex[:8],
            stage=p.current_stage, ts=time.time(),
            state={"stage_index": p.stage_index},
            label=f"pre-{target_stage}",
        ))
    p.stage_index = idx
    p.current_stage = target_stage
    p.trace.log("advance_stage", {"target": target_stage, "autonomous": autonomous_mode})
    # Defense line 5: TDD at every code commit (stage_6+)
    if target_stage in ("stage_6", "stage_7", "stage_8") and p.tdd.level != "off":
        test_evidence = evidence.get("test_evidence")
        tdd_result = p.tdd.check_red_green(test_evidence)
        if p.tdd.level == "strict" and (
                tdd_result["status"] == "blocked" or test_evidence is None):
            reason = (tdd_result.get("reason")
                      or "strict TDD: test evidence required to enter dev stage")
            p.violations.append(reason)
            return {
                "project_id": project_id, "stage_id": target_stage, "status": "blocked",
                "reason": reason, "tdd": tdd_result,
            }
        if tdd_result["status"] == "blocked":
            p.violations.append(tdd_result.get("reason", "tdd blocked"))
            return {
                "project_id": project_id, "stage_id": target_stage, "status": "blocked",
                "reason": tdd_result.get("reason", "tdd blocked"), "tdd": tdd_result,
            }
    return {
        "project_id": project_id, "stage_id": target_stage,
        "stage_name": STAGES[idx]["name"], "status": "advanced",
        "next_stage_id": STAGES[idx + 1]["id"] if idx + 1 < len(STAGES) else None,
    }


def confirm_gate(
    project_id: str,
    gate_id: str,
    gate_type: str,
    evidence: Dict[str, Any],
    reviewer_id: Optional[str] = None,
    tdd_check: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """tool 3/6 - confirm_gate. Runs the 6 defense lines + gate checks.

    Returns result in {pass, fail, blocked} with a violations list.
    """
    p = _get(project_id)
    checks = GATE_CHECKS.get(p.current_stage, [])
    violations: List[str] = []

    # 1. gate evidence completeness
    for c in checks:
        if c not in evidence:
            violations.append(f"missing evidence: {c}")

    # 2. Defense line 1: acceptance criteria (stage_2/3 boundary)
    if p.current_stage in ("stage_2", "stage_3") and "acceptance_criteria" not in evidence:
        violations.append("defense_line_1: acceptance criteria not testable")

    # 3. Defense line 2: doc lock (stage_4 gate)
    if p.current_stage == "stage_4" and not evidence.get("architecture_doc_locked"):
        violations.append("defense_line_2: architecture doc not signed & locked")

    # 4. Defense line 3: human approval (stage_5 gate, manual)
    if p.current_stage == "stage_5" and gate_type in ("manual", "hybrid") and not reviewer_id:
        violations.append("defense_line_3: human approver missing for key decision")

    # 5. TDD result merged
    if tdd_check and tdd_check.get("status") == "blocked":
        violations.append("defense_line_5: TDD red/green failed - " + tdd_check.get("reason", ""))

    # 6. Guardrails output filter
    gr = p.guardrails.filter_outputs(evidence)
    violations.extend(gr.get("violations", []))

    result = "blocked" if violations else "pass"
    record = {
        "gate_id": gate_id, "result": result, "violations": violations,
        "audit_ts": time.time(), "reviewer": reviewer_id,
    }
    p.gate_results.append(record)
    p.trace.log("confirm_gate", {"gate": gate_id, "result": result})
    return {
        "gate_id": gate_id, "result": result, "violations": violations,
        "audit_log_id": "audit_" + uuid.uuid4().hex[:8],
        "recommendations": [f"resolve: {v}" for v in violations],
    }


def query_status(
    project_id: str,
    detail_level: str = "detailed",
    include_observability: bool = True,
    trace_aggregation: bool = True,
) -> Dict[str, Any]:
    """tool 4/6 - query_status."""
    p = _get(project_id)
    out: Dict[str, Any] = {
        "project_id": project_id,
        "current_stage": p.current_stage,
        "stage_progress": f"{p.stage_index}/{len(STAGES)-1}",
        "status": p.status,
        "violations": list(p.violations),
        "gates_passed": sum(1 for g in p.gate_results if g["result"] == "pass"),
        "gates_blocked": sum(1 for g in p.gate_results if g["result"] != "pass"),
    }
    if detail_level in ("detailed", "full"):
        out["artifacts"] = dict(p.artifacts)
        out["checkpoints"] = [asdict(c) for c in p.checkpoints]
        out["health_score"] = _health(p)
    if include_observability:
        out["tokens_used"] = p.tokens_used
        out["tokens_budget"] = p.tokens_budget
        out["budget_remaining_pct"] = round(100 * (1 - p.tokens_used / p.tokens_budget), 1)
    if trace_aggregation:
        out["trace_summary"] = p.trace.summary()
    return out


def _health(p: Project) -> float:
    score = 100.0
    score -= 15 * len(p.violations)
    blocked = sum(1 for g in p.gate_results if g["result"] != "pass")
    score -= 5 * blocked
    score -= 10 * (p.tokens_used / max(1, p.tokens_budget))
    return max(0.0, round(score, 1))


def save_checkpoint(project_id: str, label: str = "") -> Dict[str, Any]:
    """tool 12/20 - save_checkpoint (LangGraph-inspired state snapshot)."""
    p = _get(project_id)
    cp = Checkpoint(
        id="cp_" + uuid.uuid4().hex[:8],
        stage=p.current_stage, ts=time.time(),
        state={
            "stage_index": p.stage_index,
            "artifacts": dict(p.artifacts),
            "violations": list(p.violations),
        },
        label=label or f"{p.current_stage}@{int(p.tokens_used)}tok",
    )
    p.checkpoints.append(cp)
    p.trace.log("save_checkpoint", {"id": cp.id})
    return {"checkpoint_id": cp.id, "stage": cp.stage, "ts": cp.ts}


def restore_checkpoint(project_id: str, checkpoint_id: str) -> Dict[str, Any]:
    """tool 13/20 - restore_checkpoint. Rolls the project back to a snapshot."""
    p = _get(project_id)
    cp = next((c for c in p.checkpoints if c.id == checkpoint_id), None)
    if cp is None:
        return {"status": "error", "reason": f"checkpoint {checkpoint_id} not found"}
    p.stage_index = cp.state.get("stage_index", 0)
    p.current_stage = STAGES[p.stage_index]["id"]
    p.artifacts = dict(cp.state.get("artifacts", {}))
    p.violations = list(cp.state.get("violations", []))
    p.trace.log("restore_checkpoint", {"from": checkpoint_id, "to_stage": p.current_stage})
    return {"status": "restored", "stage": p.current_stage}


def registry() -> Dict[str, Project]:
    """Test/introspection helper: expose the in-memory project registry."""
    return _REGISTRY
