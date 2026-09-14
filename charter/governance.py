"""Governance layer: Guardrails, TDD enforcement, rules, gates, defense lines.

This is the "how to govern" half of Charter Orchestrator - the part that
competitor engines (LangGraph, CrewAI) leave to your own tooling.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Rules (13 categories from SKILL.md chapter five) - machine-readable subset
# ---------------------------------------------------------------------------
RULES: Dict[str, Dict[str, Any]] = {
    "role_assignment": {
        "id": "role_assignment",
        "name_en": "Role Assignment",
        "name_zh": "角色分工规则",
        "max_concurrent_agents_per_stage": 4,
        "required_roles": ["lead", "architect", "developer", "reviewer"],
    },
    "permission_boundary": {
        "id": "permission_boundary",
        "name_en": "Permission Boundary",
        "name_zh": "权限边界规则",
        "dangerous_actions_require_gate": [
            "force_push", "db_drop", "prod_deploy", "rm_rf",
        ],
    },
    "communication": {
        "id": "communication",
        "name_en": "Communication Protocol",
        "name_zh": "沟通规范规则",
        "handoff_must_include": ["context", "decisions", "open_questions"],
    },
    "security_redline": {
        "id": "security_redline",
        "name_en": "Security Redline",
        "name_zh": "安全红线规则",
        "blocked_patterns": [
            r"sk-[a-zA-Z0-9]{20,}",          # API keys
            r"password\s*[:=]\s*\S+",          # plaintext passwords
            r"(?i)drop\s+table",              # destructive SQL
            r"rm\s+-rf\s+/",                 # destructive shell
        ],
    },
    "code_quality": {
        "id": "code_quality",
        "name_en": "Code Quality",
        "name_zh": "代码质量规则",
        "min_test_coverage_pct": 60,
        "max_functions_per_commit": 5,
    },
    "token_budget": {
        "id": "token_budget",
        "name_en": "Token Budget",
        "name_zh": "Token 预算规则",
        "default_budget": 100_000,
        "warn_at_pct": 80,
    },
    "rule_query": {
        "id": "rule_query",
        "name_en": "Rule Query",
        "name_zh": "治理规则查询规则",
        "queryable": True,
    },
    "checkpoint_mgmt": {
        "id": "checkpoint_mgmt",
        "name_en": "Checkpoint State Management",
        "name_zh": "Checkpoint 状态管理规则",
        "max_retained": 50,
        "auto_clean": True,
    },
    "model_dispatch": {
        "id": "model_dispatch",
        "name_en": "Multi-Model Dispatch",
        "name_zh": "多模型调度规则",
        "fallback_order": ["agnes-2.5-flash", "agnes-2.0-flash", "glm"],
        "health_check_interval_s": 300,
    },
    "tdd_discipline": {
        "id": "tdd_discipline",
        "name_en": "TDD Discipline",
        "name_zh": "TDD 纪律规则",
        "levels": ["off", "soft", "strict"],
        "strict_blocks_code_without_test": True,
    },
    "guardrails": {
        "id": "guardrails",
        "name_en": "Guardrails Safety",
        "name_zh": "Guardrails 安全护栏规则",
        "input_validation": True,
        "output_filtering": True,
    },
    "autonomous_mode": {
        "id": "autonomous_mode",
        "name_en": "Autonomous Mode",
        "name_zh": "自动驾驶模式规则",
        "high_risk_always_human": ["prod_deploy", "db_migration", "force_push"],
    },
    "event_driven": {
        "id": "event_driven",
        "name_en": "Event-Driven",
        "name_zh": "事件驱动规则",
        "max_chain_depth": 10,
    },
}


# ---------------------------------------------------------------------------
# 6 defense lines (SKILL.md chapter six)
# ---------------------------------------------------------------------------
DEFENSE_LINES: List[Dict[str, str]] = [
    {"id": "dl1", "name": "Requirement Clarification / 需求澄清",
     "checks": "acceptance criteria are testable", "at": "stage_2->3",
     "on_fail": "return to stage_2"},
    {"id": "dl2", "name": "Document Lock / 文档固化",
     "checks": "architecture doc signed & locked", "at": "stage_4 gate",
     "on_fail": "block; require doc sign-off"},
    {"id": "dl3", "name": "Human Approval / 人类审批",
     "checks": "key decisions confirmed by human", "at": "stage_5 gate",
     "on_fail": "pause for approver"},
    {"id": "dl4", "name": "Branch Isolation / 分支隔离",
     "checks": "development happens in isolated worktree", "at": "stage_6 entry",
     "on_fail": "auto-create worktree"},
    {"id": "dl5", "name": "TDD Red-Green / TDD红绿",
     "checks": "red-green-refactor cycle honored", "at": "every code commit",
     "on_fail": "block; require tests"},
    {"id": "dl6", "name": "Release Self-Check / 发版自检",
     "checks": "release checklist fully green", "at": "stage_8 gate",
     "on_fail": "block; list failed items"},
]

# Gate definitions per stage (kept in sync with core.GATE_CHECKS)
GATE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "gate_stage_0": {"stage": "stage_0", "type": "automatic",
                     "checks": ["env_report", "capability_matrix"]},
    "gate_stage_1": {"stage": "stage_1", "type": "automatic",
                     "checks": ["problem_statement", "feasibility_score"]},
    "gate_stage_2": {"stage": "stage_2", "type": "hybrid",
                     "checks": ["acceptance_criteria", "requirement_signoff"]},
    "gate_stage_3": {"stage": "stage_3", "type": "automatic",
                     "checks": ["distillation_decision", "reference_list"]},
    "gate_stage_4": {"stage": "stage_4", "type": "hybrid",
                     "checks": ["architecture_doc_locked", "tech_selection"]},
    "gate_stage_5": {"stage": "stage_5", "type": "manual",
                     "checks": ["env_ready", "ci_green", "human_approver"]},
    "gate_stage_6": {"stage": "stage_6", "type": "hybrid",
                     "checks": ["tdd_red_green", "worktree_isolated",
                                 "code_review_passed"]},
    "gate_stage_7": {"stage": "stage_7", "type": "hybrid",
                     "checks": ["integration_tests_passed", "acceptance_signed"]},
    "gate_stage_8": {"stage": "stage_8", "type": "hybrid",
                     "checks": ["release_checklist", "artifacts_built"]},
    "gate_stage_9": {"stage": "stage_9", "type": "automatic",
                     "checks": ["retro_done", "knowledge_extracted"]},
}


# ---------------------------------------------------------------------------
# Guardrails engine (OpenAI Agents SDK inspired)
# ---------------------------------------------------------------------------
class GuardrailsEngine:
    """Bidirectional guardrails: validate inputs, filter outputs, audit."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.rules = RULES["security_redline"]["blocked_patterns"]
        self._compiled = [re.compile(p) for p in self.rules]

    def validate_input(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "skipped"}
        text = str(payload)
        hits = [p.pattern for p in self._compiled if p.search(text)]
        return {
            "status": "blocked" if hits else "passed",
            "matches": hits,
        }

    def filter_outputs(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "skipped", "violations": []}
        text = str(evidence)
        violations = []
        for p in self._compiled:
            if p.search(text):
                violations.append(f"guardrail: matched blocked pattern /{p.pattern}/")
        return {"status": "blocked" if violations else "passed",
                "violations": violations}

    def audit(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Record a governance audit record (append-only in-memory)."""
        return {"audit": True, **event}


# ---------------------------------------------------------------------------
# TDD enforcer (Superpowers + autonomous-dev-team inspired)
# ---------------------------------------------------------------------------
@dataclass
class TDDEnforcer:
    level: str = "soft"   # off | soft | strict
    last_result: Optional[Dict[str, Any]] = None

    def check_red_green(self, test_evidence: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Defense line 5. test_evidence: {tests_written, tests_passed, coverage}.
        strict: code without tests blocks; soft: warns; off: passes silently.
        """
        if self.level == "off":
            return {"status": "skipped", "reason": "TDD off"}
        has_tests = bool(test_evidence and test_evidence.get("tests_written"))
        coverage = (test_evidence or {}).get("coverage", 0.0)
        min_cov = RULES["code_quality"]["min_test_coverage_pct"] / 100.0
        if has_tests and coverage >= min_cov:
            result = {"status": "passed", "coverage": coverage}
        elif self.level == "strict":
            reason = ("no tests written" if not has_tests
                      else f"coverage {coverage:.0%} < required {min_cov:.0%}")
            result = {"status": "blocked", "reason": reason,
                      "coverage": coverage}
        else:
            result = {"status": "warning",
                      "reason": "soft TDD: proceed, tests/coverage recommended"}
        self.last_result = result
        return result


# ---------------------------------------------------------------------------
# Module-level convenience wrappers matching the SKILL.md tool names
# ---------------------------------------------------------------------------
_DEFAULT_GUARDRAILS = GuardrailsEngine()
_DEFAULT_TDD = TDDEnforcer(level="soft")


def guardrails(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """tool 17/20 - guardrails. action in {validate_input, filter_output, audit}."""
    if action == "validate_input":
        return _DEFAULT_GUARDRAILS.validate_input(payload)
    if action == "filter_output":
        return _DEFAULT_GUARDRAILS.filter_outputs(payload)
    if action == "audit":
        return _DEFAULT_GUARDRAILS.audit(payload)
    raise ValueError(f"unknown guardrails action {action!r}")


def enforce_tdd(test_evidence: Optional[Dict[str, Any]],
                level: str = "soft") -> Dict[str, Any]:
    """tool 16/20 - enforce_tdd. level in {off, soft, strict}."""
    _DEFAULT_TDD.level = level
    return _DEFAULT_TDD.check_red_green(test_evidence)
