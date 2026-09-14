#!/usr/bin/env python3
"""Charter Orchestrator CLI - the "5-minute quickstart" entry point.

Run a governed multi-agent project end-to-end:
    python -m charter.cli demo

This wires together init -> advance -> TDD -> guardrails -> gate -> evaluate,
proving the framework is executable, not just a spec.
"""
from __future__ import annotations

import json
import sys

from . import (
    init_project, advance_stage, confirm_gate, query_status,
    save_checkpoint, restore_checkpoint,
    enforce_tdd, guardrails, evaluate_agent, FaultInjectionMatrix,
)


def demo() -> int:
    """A realistic governed run of a small feature project."""
    print("=" * 64)
    print("Charter Orchestrator v1.1.0 - governed run demo")
    print("=" * 64)

    # Stage 0: baseline
    r = init_project("auth-service", "software_dev",
                     "Add OAuth2 login with refresh tokens")
    pid = r["project_id"]
    print(f"\n[init] {pid} worktree={r['worktree_path']}")

    # Advance to stage 6 (development) with evidence that satisfies gates
    for stage in ["stage_1", "stage_2", "stage_3", "stage_4", "stage_5", "stage_6"]:
        ev = {
            "env_report": True, "capability_matrix": True,
            "problem_statement": "OAuth login needed", "feasibility_score": 0.9,
            "acceptance_criteria": "user can login via GitHub", "requirement_signoff": True,
            "distillation_decision": "build new", "reference_list": ["oauth2"],
            "architecture_doc_locked": True, "tech_selection": "python+sqlite",
            "env_ready": True, "ci_green": True, "human_approver": "jarvis",
            "worktree_isolated": True, "code_review_passed": True,
        }
        # Defense line 5: provide TDD evidence at dev stage
        tdd = enforce_tdd({"tests_written": True, "tests_passed": True,
                            "coverage": 0.82}, level="strict")
        adv = advance_stage(pid, stage, evidence=ev)
        gate = confirm_gate(pid, f"gate_{stage}", "hybrid", ev,
                            reviewer_id="jarvis", tdd_check=tdd)
        mark = "PASS" if gate["result"] == "pass" else "BLOCK"
        print(f"[{stage}] advance={adv['status']:8s} gate={mark:5s}"
              + (f" violations={gate['violations']}" if gate["violations"] else ""))
        if gate["result"] != "pass":
            print(f"   -> blocked: {gate['violations']}")

    # Show a TDD violation is actually caught (the framework is not a rubber stamp)
    print("\n[negative test] TDD violation must be blocked:")
    bad_tdd = enforce_tdd({"tests_written": False, "coverage": 0.1}, level="strict")
    print("   strict TDD:", bad_tdd)

    # Show a guardrail catches a secret leak
    print("\n[negative test] guardrail must catch a leaked key:")
    gr = guardrails("validate_input", {"code": "api_key = \"sk-abcdefghij1234567890ab\""})
    print("   guardrail:", gr["status"], "matches:", gr.get("matches"))

    # Checkpoint + restore
    cp = save_checkpoint(pid, "pre-release")
    print(f"\n[checkpoint] {cp['checkpoint_id']}")

    # Final status
    status = query_status(pid, detail_level="full")
    print(f"\n[status] stage={status['current_stage']} "
          f"gates passed={status['gates_passed']} blocked={status['gates_blocked']} "
          f"health={status.get('health_score')}")

    # P0 evaluation layer
    judge = evaluate_agent(pid, {
        "test_coverage": 0.82, "tests_written": True,
        "violations": [], "token_ratio": 0.4,
    })
    print(f"\n[evaluate] {judge.verdict} weighted={judge.weighted} "
          f"scores={judge.scores}")

    # P0 fault-coverage proof
    fx = FaultInjectionMatrix().report()
    print(f"\n[fault coverage] {fx['fault_seeds']} seeds, "
          f"status={fx['status']}, uncovered={fx['uncovered']}")
    print(f"   defense utilization={fx['defense_utilization']}")

    print("\n" + "=" * 64)
    print("DEMO COMPLETE - every gate, TDD, guardrail, checkpoint, eval ran.")
    print("=" * 64)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("demo", "run"):
        return demo()
    if argv[0] == "validate":
        import subprocess
        return subprocess.call([sys.executable,
                                "scripts/validate_skills.py"],
                               cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
