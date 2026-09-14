"""Executable test-suite proving the framework is real, not just a spec."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from charter import (
    init_project, advance_stage, confirm_gate, query_status,
    save_checkpoint, restore_checkpoint, enforce_tdd, guardrails,
    evaluate_agent, FaultInjectionMatrix, memory_recall, MemoryStore,
)


def _pid():
    return init_project("t", "software_dev", "obj")["project_id"]


def _ev():
    return {
        "env_report": True, "capability_matrix": True,
        "problem_statement": "x", "feasibility_score": 0.9,
        "acceptance_criteria": "x", "requirement_signoff": True,
        "distillation_decision": "new", "reference_list": ["r"],
        "architecture_doc_locked": True, "tech_selection": "py",
        "env_ready": True, "ci_green": True, "human_approver": "jarvis",
        "worktree_isolated": True, "code_review_passed": True,
        "tdd_red_green": True, "integration_tests_passed": True,
        "acceptance_signed": True, "release_checklist": True,
        "artifacts_built": True, "retro_done": True,
        "knowledge_extracted": True,
    }


def test_full_lifecycle_passes():
    pid = _pid()
    for stage in ["stage_1", "stage_2", "stage_3", "stage_4", "stage_5",
                  "stage_6", "stage_7", "stage_8", "stage_9"]:
        ev = _ev()
        adv = advance_stage(pid, stage, evidence=ev)
        assert adv["status"] in ("advanced", "blocked"), adv
        gate = confirm_gate(pid, f"gate_{stage}", "hybrid", ev, reviewer_id="j",
                            tdd_check=enforce_tdd({"tests_written": True,
                                                   "coverage": 0.9}))
        assert gate["result"] == "pass", (stage, gate)
    st = query_status(pid)
    assert st["gates_passed"] == 9, st
    assert st["current_stage"] == "stage_9"


def test_tdd_violation_blocks_dev_stage():
    from charter.core import _REGISTRY
    pid = init_project("t", "software_dev", "obj", tdd_enforcement="strict")["project_id"]
    for stage in ["stage_1", "stage_2", "stage_3", "stage_4", "stage_5"]:
        advance_stage(pid, stage, evidence=_ev())
        confirm_gate(pid, f"gate_{stage}", "hybrid", _ev(), reviewer_id="j")
    p = _REGISTRY[pid]
    assert p.tdd.level == "strict"
    # now into stage_6 without TDD evidence -> must block
    adv = advance_stage(pid, "stage_6", evidence={"test_evidence": None})
    assert adv["status"] == "blocked"
    # a *different* project with evidence should advance to stage_6 cleanly
    pid2 = init_project("t2", "software_dev", "obj", tdd_enforcement="strict")["project_id"]
    for stage in ["stage_1", "stage_2", "stage_3", "stage_4", "stage_5"]:
        advance_stage(pid2, stage, evidence=_ev())
    ok = advance_stage(pid2, "stage_6",
                       evidence={"test_evidence": {"tests_written": True, "coverage": 0.9}})
    assert ok["status"] == "advanced", ok


def test_guardrail_catches_secrets():
    r = guardrails("validate_input", {"code": "k='sk-" + "a" * 30 + "'"})
    assert r["status"] == "blocked" and r["matches"]


def test_guardrail_allows_clean():
    r = guardrails("validate_input", {"code": "x = 1 + 2"})
    assert r["status"] == "passed"


def test_backward_advance_blocked():
    pid = _pid()
    advance_stage(pid, "stage_3", evidence=_ev())
    r = advance_stage(pid, "stage_1")  # backward
    assert r["status"] == "blocked"


def test_checkpoint_restore():
    pid = _pid()
    advance_stage(pid, "stage_2", evidence=_ev())
    cp = save_checkpoint(pid, "label")
    advance_stage(pid, "stage_4", evidence=_ev())
    r = restore_checkpoint(pid, cp["checkpoint_id"])
    assert r["status"] == "restored" and r["stage"] == "stage_2"


def test_evaluate_agent_pass_and_fail():
    pid = _pid()
    good = evaluate_agent(pid, {"test_coverage": 0.9, "tests_written": True,
                                "violations": [], "token_ratio": 0.3})
    assert good.passed
    bad = evaluate_agent(pid, {"test_coverage": 0.1, "tests_written": False,
                               "violations": ["secret_leak"], "token_ratio": 0.99})
    assert not bad.passed


def test_fault_matrix_full_coverage():
    rep = FaultInjectionMatrix().report()
    assert rep["status"] == "full" and not rep["uncovered"]
    assert rep["fault_seeds"] == 14


def test_memory_recall():
    store = MemoryStore()
    store.remember("agentA", "decided to use SQLite for the cache layer")
    store.remember("agentA", "chose Redis for session store")
    hits = memory_recall("agentA", "cache", limit=3, store=store)
    assert any("SQLite" in h["content"] for h in hits)
    # cross-agent isolation
    assert memory_recall("agentB", "cache", limit=3, store=store) == []


def test_query_status_includes_observability():
    pid = _pid()
    st = query_status(pid, include_observability=True)
    assert "tokens_used" in st and "trace_summary" in st
