"""Evaluation layer: LLM-as-judge scoring + fault-injection coverage matrix.

Closes the biggest v1.0 gap identified in the peer review (Red Hat 2026-07
"7 missing production capabilities" + Microsoft agent eval + MAST fault
taxonomy). evaluate_agent gives a runnable quality gate; FaultInjectionMatrix
maps 14 fault seeds onto the 6 defense lines to prove coverage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Fault taxonomy (14 seeds, MAST/OrchestraBench inspired)
# ---------------------------------------------------------------------------
FAULT_SEEDS: List[str] = [
    "ambiguous_delegation", "missing_context", "tool_fault", "schema_drift",
    "prompt_injection", "budget_exhaustion", "model_timeout", "cascading_error",
    "stale_checkpoint", "permission_escalation", "secrets_leak",
    "off_spec_code", "flaky_test", "infinite_loop",
]

# Which defense line catches which fault (from SKILL.md ch. six + peer review)
FAULT_COVERAGE: Dict[str, List[str]] = {
    "ambiguous_delegation": ["dl1", "dl3"],
    "missing_context": ["dl1"],
    "tool_fault": ["dl5", "dl6"],
    "schema_drift": ["dl6"],
    "prompt_injection": ["dl3", "dl6"],
    "budget_exhaustion": ["dl6"],
    "model_timeout": ["dl6"],
    "cascading_error": ["dl2", "dl6"],
    "stale_checkpoint": ["dl2"],
    "permission_escalation": ["dl3"],
    "secrets_leak": ["dl6"],
    "off_spec_code": ["dl5"],
    "flaky_test": ["dl5"],
    "infinite_loop": ["dl6"],
}

# Defense line ids
DEFENSE_IDS = ["dl1", "dl2", "dl3", "dl4", "dl5", "dl6"]


class FaultInjectionMatrix:
    """Prove that every fault seed is covered by at least one defense line."""

    def __init__(self) -> None:
        self.coverage = dict(FAULT_COVERAGE)

    def report(self) -> Dict[str, Any]:
        uncovered = [f for f, dls in self.coverage.items() if not dls]
        # which defense lines are exercised
        dl_usage: Dict[str, int] = {d: 0 for d in DEFENSE_IDS}
        for dls in self.coverage.values():
            for d in dls:
                dl_usage[d] += 1
        return {
            "fault_seeds": len(self.coverage),
            "uncovered": uncovered,
            "defense_utilization": dl_usage,
            "coverage_ratio": round(
                (len(self.coverage) - len(uncovered)) / max(1, len(self.coverage)), 2
            ),
            "status": "full" if not uncovered else "gaps",
        }

    def add_coverage(self, fault: str, defense_lines: List[str]) -> None:
        self.coverage[fault] = self.coverage.get(fault, []) + [
            d for d in defense_lines if d not in self.coverage.get(fault, [])
        ]


# ---------------------------------------------------------------------------
# LLM-as-judge evaluator (Microsoft agent-eval inspired)
# ---------------------------------------------------------------------------
JUDGE_DIMENSIONS = ["spec_compliance", "code_quality", "test_adequacy",
                    "efficiency", "safety"]


@dataclass
class JudgeScore:
    project_id: str
    scores: Dict[str, float]
    weighted: float
    passed: bool
    verdict: str
    details: Dict[str, Any] = field(default_factory=dict)


def evaluate_agent(
    project_id: str,
    artifacts: Dict[str, Any],
    judge: Optional[Callable[[str, Dict[str, Any]], float]] = None,
    threshold: float = 0.7,
) -> JudgeScore:
    """tool: evaluate_agent - P0 evaluation layer.

    `judge` is a callable (prompt, artifacts) -> 0..1 score. When None, a
    deterministic heuristic judge is used (works offline, no LLM key needed):
    rewards tests written, coverage, no violations, budget respected.
    """
    if judge is None:
        judge = _heuristic_judge
    scores: Dict[str, float] = {}
    for dim in JUDGE_DIMENSIONS:
        scores[dim] = round(judge(dim, artifacts), 3)
    weights = {"spec_compliance": .25, "code_quality": .25,
               "test_adequacy": .25, "efficiency": .1, "safety": .15}
    weighted = sum(scores[d] * w for d, w in weights.items())
    passed = weighted >= threshold
    verdict = ("pass" if passed else "fail")
    return JudgeScore(
        project_id=project_id, scores=scores,
        weighted=round(weighted, 3), passed=passed, verdict=verdict,
        details={"threshold": threshold, "weights": weights},
    )


def _heuristic_judge(dim: str, artifacts: Dict[str, Any]) -> float:
    """Offline deterministic judge - swap for an LLM call in production."""
    cov = artifacts.get("test_coverage", 0.0)
    violations = artifacts.get("violations", [])
    token_ratio = artifacts.get("token_ratio", 0.5)
    if dim == "spec_compliance":
        return 1.0 if not violations else max(0.0, 1.0 - 0.2 * len(violations))
    if dim == "code_quality":
        return min(1.0, cov * 1.2)
    if dim == "test_adequacy":
        return 1.0 if artifacts.get("tests_written") and cov >= 0.6 else 0.4
    if dim == "efficiency":
        return 1.0 if token_ratio <= 0.8 else 0.5
    if dim == "safety":
        leaks = [v for v in violations if "secret" in str(v).lower()
                 or "leak" in str(v).lower()]
        return 0.0 if leaks else 1.0
    return 0.5
