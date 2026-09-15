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

    # ---- v2.0 layers ----
    print("\n" + "-" * 64)
    print("v2.0 layers")
    print("-" * 64)

    from .identity import IdentityRegistry, issue_agent, sign_tool_call, verify_tool_call
    from .vector_memory import VectorMemory
    from .templates import list_templates, apply_template
    from .otel_export import to_otlp_json, prometheus_text

    # 1) Cryptographic identity: sign a tool call, verify, block replay
    reg = IdentityRegistry(root_key="demo-root")
    issue_agent("dev-1", ["execute_in_sandbox", "advance_stage"], registry=reg)
    call = sign_tool_call("dev-1", "execute_in_sandbox", {"cmd": "pytest"}, registry=reg)
    v1 = verify_tool_call(call, {"cmd": "pytest"}, registry=reg)
    v2 = verify_tool_call(call, {"cmd": "pytest"}, registry=reg)  # replay
    print(f"[identity] first verify={v1['ok']}  replay verify={v2['ok']}"
          f" (problems={v2['problems']})")

    # 2) Vector memory: semantic recall
    vm = VectorMemory(path=":memory:", dim=128)
    vm.remember("dev-1", "we decided SQLite is the cache layer")
    vm.remember("dev-1", "OAuth2 login flow returns 401 on expired token")
    hits = vm.recall("dev-1", "cache storage choice", limit=1)
    print(f"[vector] recall 'cache storage choice' -> "
          f"'{hits[0]['content']}' (score={hits[0]['score']})")

    # 3) SOP template marketplace: apply a domain template
    tpl_names = [t["name"] for t in list_templates()]
    cfg = apply_template({"tdd_enforcement": "soft"}, "finance")
    print(f"[templates] available={tpl_names}")
    print(f"[templates] finance override -> tdd={cfg['tdd_enforcement']} "
          f"budget={cfg['token_budget']}")

    # 4) OTel + Prometheus export from the project trace
    p = __import__("charter").core._REGISTRY[pid]
    otlp = to_otlp_json(p.trace.spans)
    spans = otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]
    prom = prometheus_text(p.trace.spans, pid)
    print(f"[otel] {len(spans)} spans exported as OTLP/JSON")
    print(f"[otel] prometheus sample:\n  {prom.strip().splitlines()[2]}")

    # ---- v2.1 hardening ----
    print("\n" + "-" * 64)
    print("v2.1 hardening")
    print("-" * 64)

    from charter.grafana import live_metrics_demo, dashboard_json
    from charter.template_pr import TemplateMarketplace, validate_template, render_pr

    # 1) Real Grafana provisioning bundle
    bundle = live_metrics_demo()
    print(f"[grafana] data sources: {bundle['prometheus_ds']['datasources'][0]['type']}, "
          f"{bundle['tempo_ds']['datasources'][0]['type']} | "
          f"dashboard panels: {len(bundle['dashboard']['panels'])}")

    # 2) X.509 signed tool call (if cryptography available)
    import importlib.util
    if importlib.util.find_spec("cryptography"):
        from charter import x509_issue, x509_sign, x509_verify
        x509_issue("dev-1", ["execute_in_sandbox"])
        call = x509_sign("dev-1", "execute_in_sandbox", {"cmd": "pytest"})
        ok = x509_verify(call, {"cmd": "pytest"})
        print(f"[x509] signed call verify={ok['ok']} agent={ok.get('agent')}")
    else:
        print("[x509] cryptography not installed -> HMAC fallback (charter.identity) in use")

    # 3) Template PR governance: validate + render
    spec = {"name": "logistics", "label": "Logistics / Supply Chain",
            "stage_gates": {"stage_8": ["release_checklist", "logistics_audit"]},
            "tdd_enforcement": "soft", "token_budget": 90000,
            "guardrail_extra_patterns": [r"(?i)dangerous"],
            "audit_required_stages": ["stage_8"]}
    probs = validate_template(spec)
    print(f"[template-pr] validate '{spec['name']}' -> problems={probs}")
    m = TemplateMarketplace()
    pr = m.propose(spec, author="community")
    m.approve(pr.pr_id, "reviewer-1")
    merged = m.merge(pr.pr_id)
    print(f"[template-pr] merged '{merged}' (now loadable)")

    print("\n" + "=" * 64)
    print("DEMO COMPLETE - v1.1 + v2.0 + v2.1 all layers ran "
          "(governance, OTel, identity, vector, templates, X.509, Grafana).")
    print("=" * 64)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("demo", "run"):
        # v3.13: "demo --gov" runs the governed-orchestration chain;
        # "demo" (or "run") keeps the classic governed-run flow.
        if len(argv) > 1 and argv[1] == "--gov":
            return demo_governance()
        return demo()
    if argv[0] == "validate":
        import subprocess
        return subprocess.call([sys.executable,
                                "scripts/validate_skills.py"],
                               cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(__doc__)
    return 1



def demo_governance() -> int:
    """v3.13: end-to-end demo of the four governance modules + MCP gov tools."""
    from charter import (
        ValidationGateway, CircuitBreaker, Critic, CriticPlan, CriticStep,
        SemanticTracer, TaskProfile, ModelRouter, SemanticCache,
        repair_and_rerun,
    )
    from charter.demo_skill import _demo_governance

    print("=" * 64)
    print("Charter Orchestrator v3.13 - governance demo (--gov)")
    print("=" * 64)

    # Classic chain
    rep = _demo_governance()
    print("[governance] critic sound:", rep["critic"]["sound"],
          "| gateway passed:", rep["gateway"]["passed"],
          "| hallucination_detected:", rep["semantic_trace"]["hallucination_detected"])
    print("[routing] easy:", rep["model_routing"]["easy"],
          "| hard:", rep["model_routing"]["hard"])

    # v3.12 closed loop + v3.13 agent-rerun loop
    plan = CriticPlan(plan_id="gov-demo", goal="report",
                      steps=[CriticStep(id="fetch", produces=["data"]),
                             CriticStep(id="write", depends_on=["fetch"], produces=["report"])])
    broken = CriticPlan(plan_id="gov-demo-broken", goal="report",
                        steps=[CriticStep(id="a", depends_on=["b"]),
                               CriticStep(id="b", depends_on=["a"])])
    closed = Critic().reflect_until_sound(broken, None, max_rounds=3)
    print("[closed-loop] converged:", closed.converged, "rounds:", closed.rounds)

    calls = []
    rerun = repair_and_rerun(
        broken, executor=lambda step: calls.append(step.id) or {"done": True},
        max_rounds=3)
    print("[repair-and-rerun] converged:", rerun.converged,
          "executor calls:", calls)
    print("\nOK: governance demo complete (4 modules + 2 closed-loop modes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    main()
