"""Tests for charter/critic_agent (v3.11 global reflector + repair)."""
from __future__ import annotations

import charter.critic_agent as ca


def _plan():
    return ca.CriticPlan(plan_id="p1", goal="industry report",
                         steps=[
                             ca.CriticStep(id="fetch", name="research", produces=["data"]),
                             ca.CriticStep(id="analyze", name="growth", depends_on=["fetch"],
                                           produces=["insight"]),
                             ca.CriticStep(id="write", name="report", depends_on=["analyze"],
                                           produces=["report"]),
                         ])


def test_pre_check_clean_plan():
    rep = ca.Critic().reflect(_plan())
    assert rep.sound is True
    assert rep.pre_findings == []


def test_pre_check_dangling_dependency():
    p = _plan()
    p.steps[1].depends_on.append("ghost")
    rep = ca.Critic().reflect(p)
    assert any(f["kind"] == "dangling_dependency" for f in rep.pre_findings)
    assert rep.sound is False
    # a repair was produced (not just an error)
    assert rep.repairs, "expected a repair for the dangling dependency"
    assert rep.repairs[0]["action"] == "insert_step"


def test_pre_check_cycle():
    p = ca.CriticPlan(plan_id="cyc", steps=[
        ca.CriticStep(id="a", depends_on=["b"], produces=["x"]),
        ca.CriticStep(id="b", depends_on=["a"], produces=["y"]),
    ])
    rep = ca.Critic().reflect(p)
    assert any(f["kind"] == "cycle" for f in rep.pre_findings)
    assert rep.sound is False
    assert any(r["action"] == "break_cycle" for r in rep.repairs)


def test_pre_check_duplicate_produces():
    p = ca.CriticPlan(plan_id="dup", steps=[
        ca.CriticStep(id="a", produces=["data"]),
        ca.CriticStep(id="b", produces=["data"]),
    ])
    rep = ca.Critic().reflect(p)
    assert any(f["kind"] == "duplicate_produces" for f in rep.pre_findings)


def test_post_audit_missing_required_output():
    p = _plan()
    # outputs dict marks analyze as explicit None
    rep = ca.Critic().reflect(p, {"fetch": {"data": 1}, "analyze": None,
                                 "write": {"report": "x"}})
    assert any(f["kind"] == "explicit_none" for f in rep.post_findings)


def test_post_audit_custom_rule():
    def rule(plan, step_id, out, outputs):
        if step_id == "analyze" and isinstance(out, dict) and out.get("growth") == 0.20:
            return {"kind": "implausible", "severity": "critical",
                    "message": "growth 20% conflicts with Q1 decline",
                    "detail": {"growth": out.get("growth")}}
        return None
    c = ca.Critic(rules=[rule])
    p = _plan()
    rep = c.reflect(p, {"fetch": {"data": 1}, "analyze": {"growth": 0.20},
                       "write": {"report": "x"}})
    assert any(f["kind"] == "implausible" for f in rep.post_findings)
    assert rep.sound is False


def test_repair_returns_structured_patch():
    p = _plan()
    p.steps[1].depends_on.append("ghost")
    c = ca.Critic()
    rep = c.reflect(p)
    assert rep.repairs, "repair should be generated for critical findings"
    patch = rep.repairs[0]
    assert isinstance(patch, dict) and patch.get("action")
