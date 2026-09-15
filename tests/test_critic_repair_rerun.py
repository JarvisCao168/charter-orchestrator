"""v3.13: Critic repair -> agent-rerun closed loop (repair_and_rerun)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from charter import CriticPlan, CriticStep, repair_and_rerun


def _cyclic_plan():
    return CriticPlan(plan_id="p", goal="g", steps=[
        CriticStep(id="a", depends_on=["b"]),
        CriticStep(id="b", depends_on=["a"]),
    ])


def test_repair_and_rerun_calls_executor_each_round():
    calls = []

    def executor(step):
        calls.append(step.id)
        return {"done": True}

    report = repair_and_rerun(_cyclic_plan(), executor=executor, max_rounds=3)
    assert report.converged is True
    assert report.rounds >= 1
    # executor ran for both steps at least once
    assert "a" in calls and "b" in calls
    # history records the rerun count
    assert report.history
    assert "rerun_steps" in report.history[0]


def test_repair_and_rerun_no_executor_degrades_to_reflect_loop():
    report = repair_and_rerun(_cyclic_plan(), executor=None, max_rounds=3)
    assert report.converged is True
    assert report.final_plan is not None


def test_repair_and_rerun_executor_exception_recorded():
    def flaky(step):
        raise RuntimeError("agent crashed")

    report = repair_and_rerun(_cyclic_plan(), executor=flaky, max_rounds=2)
    # exceptions in the executor must not propagate; the loop still converges
    assert report.converged is True
    assert report.rounds >= 1


def test_repair_and_rerun_record_history_toggle():
    report = repair_and_rerun(_cyclic_plan(), executor=lambda s: {},
                              max_rounds=2, record_history=False)
    assert report.history == []
    assert report.converged is True
