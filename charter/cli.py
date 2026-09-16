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
    if argv[0] == "metrics-watch":
        # v3.17: terminal dashboard for the MCP /metrics endpoint
        #   python -m charter.cli metrics-watch --url http://127.0.0.1:8765/metrics --interval 1.0
        return metrics_watch(argv[1:])
    if argv[0] == "attach-audit":
        # v3.17: post a --trace-out audit report to a GitHub PR
        #   python -m charter.cli attach-audit --report gov_audit.json --pr 123 [--repo owner/name] [--gh base]
        return attach_audit_to_pr(argv[1:])
    if argv[0] == "audit-loop":
        # v3.18: periodic governance audit + auto-attach to PR
        #   python -m charter.cli audit-loop --pr 42 [--repo o/n] [--interval 30] [--cycles 0]
        return audit_loop(argv[1:])
    if argv[0] == "validate-stress-report":
        # v3.19: validate a CAS stress JSON report
        #   python -m charter.cli validate-stress-report cas_report.json
        return validate_stress_report(argv[1:])
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
    print("Charter Orchestrator v3.21 - governance demo (--gov)")
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

    # v3.14: --live mode: real cross-process L3 hit via a temp HTTP KV gateway
    import sys
    if "--live" in sys.argv:
        rep_live = _demo_governance_live()
        print("[live L3] ", rep_live)
    if "--live-pipeline" in sys.argv:
        rep_pipe = _demo_pipeline_l3_live()
        print("[live pipeline L3] ", rep_pipe)
    # v3.16: --trace-out file.json : write a machine-readable semantic audit report
    trace_out = None
    for idx, a in enumerate(sys.argv):
        if a == "--trace-out" and idx + 1 < len(sys.argv):
            trace_out = sys.argv[idx + 1]
    if trace_out:
        from charter import SemanticTracer, export_audit_report
        tracer = SemanticTracer(threshold=0.2)
        # record the same good/bad spans the classic demo records
        tracer.record("audit-good", "query the 2024 market size",
                      "the 2024 market size is 500 billion", tool="demo")
        tracer.record("audit-bad", "query the 2024 market size",
                      "the weather is nice today", tool="demo")
        path = export_audit_report(tracer, trace_out)
        print(f"[audit] wrote {path} ({tracer.summary()['spans']} spans, "
              f"{tracer.summary()['hallucinations']} hallucinations)")
    suffixes = []
    if "--live" in sys.argv:
        suffixes.append("live L3")
    if "--live-pipeline" in sys.argv:
        suffixes.append("live pipeline L3")
    if trace_out:
        suffixes.append("audit report")
    print("\nOK: governance demo complete (4 modules + 2 closed-loop modes"
          + (f" + {', '.join(suffixes)}" if suffixes else ")"))
    return 0



def _demo_pipeline_l3_live() -> dict:
    """v3.16: plan_pipeline decision cache shared across two processes via L3.

    A reference KV gateway hosts the pipeline SemanticCache L3; two separate
    python subprocesses call the same plan_pipeline plan - the second process
    must serve its answer from the L3 (cached: True), proving the decision
    cache is genuinely distributed, not local.
    """
    import os as _os
    import subprocess
    import sys as _sys

    from charter import reference_kv_gateway
    srv, url, _store = reference_kv_gateway()

    base_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    plan_obj = {"plan_id": "l3-pipe", "goal": "g",
                "steps": [{"id": "a"}, {"id": "b", "depends_on": ["a"]},
                           {"id": "c", "depends_on": ["b"]}],
                "closed_loop": True}

    import pickle as _pk
    plan_lit = _pk.dumps(plan_obj)

    def node_script(label):
        return (
            "import sys, pickle\n"
            f"sys.path.insert(0, {base_dir!r})\n"
            "from charter import configure_pipeline_cache, make_remote_backend\n"
            f"configure_pipeline_cache(remote=make_remote_backend('http', {url!r}, timeout_s=3.0))\n"
            "from charter.mcp_server import run_tool\n"
            f"plan = pickle.loads({plan_lit!r})\n"
            "r = run_tool('plan_pipeline', {'plan': plan})\n"
            f"print({label!r}, 'cached:', r['result'].get('cached', False), "
            "'routing:', len(r['result']['routing']))\n"
        )

    py = _sys.executable
    n1 = subprocess.run([py, "-c", node_script("node-a")],
                        capture_output=True, text=True, timeout=90, cwd=base_dir)
    n2 = subprocess.run([py, "-c", node_script("node-b")],
                        capture_output=True, text=True, timeout=90, cwd=base_dir)
    srv.shutdown()
    return {
        "gateway_url": url,
        "node_a": n1.stdout.strip(), "node_a_exit": n1.returncode,
        "node_b": n2.stdout.strip(), "node_b_exit": n2.returncode,
        "node_a_stderr": n1.stderr.strip()[-200:] if n1.returncode else "",
        "node_b_stderr": n2.stderr.strip()[-200:] if n2.returncode else "",
        "shared_l3_hit": n2.returncode == 0 and "cached: True" in n2.stdout
                         and "cached: False" in n1.stdout,
    }

def _parse_metrics(text: str) -> dict:
    """Parse a Prometheus text exposition into {metric_name{labels}: float}."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # name{labels} value
        if "{" in line:
            name, rest = line.split("{", 1)
            if "}" in rest:
                labels, tail = rest.split("}", 1)
                val = tail.strip()
                if val:
                    out[name + "{" + labels + "}"] = float(val)
        else:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    out[parts[0]] = float(parts[1])
                except ValueError:
                    pass
    return out


def metrics_watch(argv: list) -> int:
    """v3.17: terminal dashboard that polls an MCP /metrics endpoint.

    v3.18: dual-source — when ``--sse`` is given, the dashboard also
    subscribes to the SSE ``/mcp/sse?stream=metrics`` event stream and
    updates in real time without polling. Both sources are merged; SSE
    events take priority (they carry the freshest snapshot). Ctrl-C to stop.
    """
    import time as _t
    import threading as _th
    import urllib.request

    url = None
    sse_url = None
    interval = 2.0
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--url", "-u") and i + 1 < len(argv):
            url = argv[i + 1]; i += 2
        elif a in ("--sse",) and i + 1 < len(argv):
            sse_url = argv[i + 1]; i += 2
        elif a == "--interval" and i + 1 < len(argv):
            interval = float(argv[i + 1]); i += 2
        else:
            i += 1
    if not url and not sse_url:
        print("usage: python -m charter.cli metrics-watch --url http://host:port/metrics [--sse http://host:port/mcp/sse?stream=metrics] [--interval 2.0]")
        return 2
    keys = [
        "charter_mcp_gate_pass_total",
        "charter_mcp_gate_fail_total",
        "charter_mcp_tracer_spans_total",
        "charter_mcp_tracer_hallucinations_total",
        "charter_mcp_tracer_drift_sum",
    ]
    prev = {}
    latest_snap: dict = {}

    def _render(snap: dict, source: str) -> None:
        gate_p = snap.get("charter_mcp_gate_pass_total", 0.0)
        gate_f = snap.get("charter_mcp_gate_fail_total", 0.0)
        spans = snap.get("charter_mcp_tracer_spans_total", 0.0)
        hall = snap.get("charter_mcp_tracer_hallucinations_total", 0.0)
        drift = snap.get("charter_mcp_tracer_drift_sum", 0.0)
        delta = ""
        if prev:
            d = lambda k: snap.get(k, 0.0) - prev.get(k, 0.0)
            delta = (f"  \u0394 gate+{d('charter_mcp_gate_pass_total'):g}/"
                     f"-{d('charter_mcp_gate_fail_total'):g} "
                     f"spans+{d('charter_mcp_tracer_spans_total'):g} "
                     f"hall+{d('charter_mcp_tracer_hallucinations_total'):g}")
        # v3.19: per-tool breakdown (top 3 by gate_fail)
        tool_lines = []
        for tool, cnt in sorted(
                {k: v for k, v in snap.items() if k.startswith('charter_mcp_gate_fail_total{tool=')}.items(),
                key=lambda x: -v):
            tool_lines.append(f"{k.split('tool=')[1].rstrip('}')}:{cnt:g}")
            if len(tool_lines) >= 3:
                break
        tool_str = " | " + ", ".join(tool_lines) if tool_lines else ""
        print(f"\r[gov:{source}] gate pass={gate_p:g} fail={gate_f:g} | "
              f"spans={spans:g} halluc={hall:g} drift={drift:.3f}"
              f"{delta}{tool_str}   ", end="", flush=True)

    sse_stop = _th.Event()

    def _sse_consumer() -> None:
        """v3.18: SSE event stream consumer (thread)."""
        import json as _json
        try:
            req = urllib.request.Request(sse_url, headers={"User-Agent": "charter-metrics-watch",
                                                           "Accept": "text/event-stream"})
            with urllib.request.urlopen(req, timeout=None) as r:
                buf = ""
                event_type = ""
                data_lines: list = []
                while not sse_stop.is_set():
                    chunk = r.read(512).decode("utf-8", errors="replace")
                    if not chunk:
                        break
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line[5:].lstrip())
                        elif line == "":
                            if event_type == "metrics" and data_lines:
                                text = "\n".join(data_lines)
                                snap = _parse_metrics(text)
                                if snap:
                                    _render(snap, "sse")
                                data_lines = []
                                event_type = ""
                            else:
                                data_lines = []
                                event_type = ""
        except Exception:
            pass

    sse_thread = None
    if sse_url:
        sse_thread = _th.Thread(target=_sse_consumer, daemon=True)
        sse_thread.start()

    try:
        while True:
            if url:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "charter-metrics-watch"})
                    with urllib.request.urlopen(req, timeout=interval * 2 + 1) as r:
                        text = r.read().decode()
                    snap = _parse_metrics(text)
                    if snap:
                        _render(snap, "poll")
                        prev = snap
                except Exception:
                    pass
            if not url:
                # SSE-only mode: just sleep and let the thread render
                _t.sleep(interval)
            else:
                _t.sleep(interval)
    except KeyboardInterrupt:
        sse_stop.set()
        print("\nmetrics-watch stopped")
        return 0
    except Exception as e:
        sse_stop.set()
        print(f"metrics-watch error: {e}")
        return 1


def attach_audit_to_pr(argv: list) -> int:
    """v3.17: post a ``--trace-out`` audit report to a GitHub PR as a comment.

    Uses the local ``gh`` CLI if available (``gh pr comment``), otherwise
    falls back to the GitHub REST API with CHARTER_GITHUB_TOKEN / GITHUB_TOKEN
    (``POST /repos/{owner}/{repo}/issues/{number}/comments``). The report is
    embedded as a fenced JSON code block with a short summary header.
    """
    import json as _json
    import os as _os
    import subprocess as _sp

    report = None
    pr = None
    repo = None
    token = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--report",) and i + 1 < len(argv):
            report = argv[i + 1]; i += 2
        elif a in ("--pr",) and i + 1 < len(argv):
            pr = argv[i + 1]; i += 2
        elif a in ("--repo",) and i + 1 < len(argv):
            repo = argv[i + 1]; i += 2
        elif a in ("--token",) and i + 1 < len(argv):
            token = argv[i + 1]; i += 2
        else:
            print(f"unknown arg: {a}"); i += 1
    if not report or not pr:
        print("usage: python -m charter.cli attach-audit --report gov_audit.json --pr 123 "
              "[--repo owner/name] [--token gh_xxx]")
        return 2
    if not _os.path.isfile(report):
        print(f"report not found: {report}"); return 2
    doc = _json.load(open(report, encoding="utf-8"))
    summary = doc.get("summary", {})
    body = ("### Charter semantic audit report\n\n"
            f"- spans: {summary.get('spans')}\n"
            f"- hallucinations: {summary.get('hallucinations')}\n"
            f"- avg similarity: {summary.get('avg_similarity')}\n\n"
            "```json\n" + _json.dumps(doc, ensure_ascii=False, indent=2) + "\n```")

    # 1) prefer the gh CLI
    gh = None
    for cand in ("gh", "gh.exe"):
        try:
            _sp.run([cand, "--version"], capture_output=True, timeout=10)
            gh = cand
            break
        except (FileNotFoundError, _sp.TimeoutExpired):
            continue
    if gh and repo is None:
        r2 = _sp.run([gh, "repo", "view", "--json", "nameWithOwner"],
                     capture_output=True, text=True, timeout=30)
        if r2.returncode == 0:
            repo = _json.loads(r2.stdout).get("nameWithOwner")
    if gh and repo:
        r3 = _sp.run([gh, "api",
                      f"repos/{repo}/issues/{pr}/comments",
                      "-f", "body=" + body[:50000]],
                     capture_output=True, text=True, timeout=60)
        if r3.returncode == 0:
            print(f"posted audit report to PR #{pr} via gh ({repo})")
            return 0
    # 2) REST API fallback
    tok = token or _os.environ.get("CHARTER_GITHUB_TOKEN") or _os.environ.get("GITHUB_TOKEN")
    if not repo:
        print("--repo owner/name is required for the REST fallback"); return 2
    if not tok:
        print("no gh CLI available and no token (CHARTER_GITHUB_TOKEN/GITHUB_TOKEN)"); return 2
    import urllib.request
    payload = {"body": body[:500000]}
    req = _urllib_request(
        f"https://api.github.com/repos/{repo}/issues/{pr}/comments",
        data=_json.dumps(payload).encode(), token=tok, method="POST")
    print(f"posted audit report to {repo} PR #{pr} via REST API")
    return 0


def _urllib_request(url, data=None, token=None, method="GET"):
    import urllib.request, urllib.error, json as _j
    h = {"User-Agent": "charter-orchestrator", "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
        return r.status, (_j.loads(raw) if raw else None)

def _webhook_post(payload: dict, url: str, timeout_s: int = 15) -> tuple:
    """v3.20: POST a JSON payload to a Slack/Discord/Feishu webhook.

    Returns ``(ok: bool, status_or_error: str)``. Stdlib-only.
    """
    import json as _json
    import urllib.request
    body = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "charter-orchestrator"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return True, str(r.status)
    except Exception as e:
        return False, str(e)[:200]


# v3.21: in-memory webhook retry queue (exponential backoff, max 3 attempts)
_WEBHOOK_RETRY_QUEUE: list = []  # [(payload, url, attempt, next_retry_ts)]
_WEBHOOK_RETRY_LOCK = __import__("threading").Lock()
_WEBHOOK_MAX_ATTEMPTS = 3


def _webhook_enqueue_retry(payload: dict, url: str, attempt: int, delay_s: float) -> None:
    """v3.21: add a failed webhook post to the retry queue."""
    import time as _t
    next_ts = _t.time() + delay_s
    with _WEBHOOK_RETRY_LOCK:
        _WEBHOOK_RETRY_QUEUE.append((payload, url, attempt, next_ts))


def _webhook_process_retries() -> int:
    """v3.21: drain the retry queue; returns the number of successfully retried items."""
    import time as _t
    now = _t.time()
    with _WEBHOOK_RETRY_LOCK:
        pending = [item for item in _WEBHOOK_RETRY_QUEUE if item[3] <= now]
        remaining = [item for item in _WEBHOOK_RETRY_QUEUE if item[3] > now]
        _WEBHOOK_RETRY_QUEUE[:] = remaining
    retried = 0
    for payload, url, attempt, _ in pending:
        ok, _msg = _webhook_post(payload, url, timeout_s=15)
        if ok:
            retried += 1
        else:
            new_attempt = attempt + 1
            if new_attempt <= _WEBHOOK_MAX_ATTEMPTS:
                delay = min(2 ** new_attempt, 30.0)  # exponential backoff: 2s, 4s, 8s...
                _webhook_enqueue_retry(payload, url, new_attempt, delay)
            else:
                print(f"webhook: giving up after {attempt} retries ({url})")
    return retried


def audit_loop(argv: list) -> int:
    """v3.18: periodic governance audit + auto-attach to a PR.

    v3.19: adds ``--metrics-url`` (health check) and ``--dry-run``.
    Each cycle: (1) GET the metrics URL to confirm the server is online;
    if offline, skip the cycle and log it. (2) Run ``demo --gov
    --trace-out``. (3) Post the report to the PR (skipped in --dry-run).

    Usage:
      python -m charter.cli audit-loop --pr 42 --repo o/n --interval 30
        [--cycles 0] [--out-dir /tmp] [--metrics-url http://host:port/metrics]
        [--dry-run]
    """
    import time as _t
    import os as _os
    import subprocess as _sp
    import sys as _sys
    import urllib.request as _ur

    pr = None
    repo = None
    interval = 30.0
    cycles = 0
    out_dir = None
    metrics_url = None
    dry_run = False
    webhook_url = None
    webhook_template = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--pr" and i + 1 < len(argv):
            pr = argv[i + 1]; i += 2
        elif a == "--repo" and i + 1 < len(argv):
            repo = argv[i + 1]; i += 2
        elif a == "--interval" and i + 1 < len(argv):
            interval = float(argv[i + 1]); i += 2
        elif a == "--cycles" and i + 1 < len(argv):
            cycles = int(argv[i + 1]); i += 2
        elif a == "--out-dir" and i + 1 < len(argv):
            out_dir = argv[i + 1]; i += 2
        elif a == "--metrics-url" and i + 1 < len(argv):
            metrics_url = argv[i + 1]; i += 2
        elif a == "--dry-run":
            dry_run = True; i += 1
        elif a == "--webhook-url" and i + 1 < len(argv):
            webhook_url = argv[i + 1]; i += 2
        elif a == "--webhook-template" and i + 1 < len(argv):
            webhook_template = argv[i + 1]; i += 2
        else:
            i += 1
    if not pr:
        print("usage: python -m charter.cli audit-loop --pr 42 [--repo o/n] [--interval 30]"
              " [--cycles 0] [--out-dir /tmp] [--metrics-url http://host:port/metrics] [--dry-run]")
        return 2
    if out_dir is None:
        import tempfile
        out_dir = tempfile.mkdtemp(prefix="charter-audit-")
    _os.makedirs(out_dir, exist_ok=True)
    mode = "dry-run" if dry_run else "live"
    print(f"audit-loop: PR #{pr} interval={interval}s cycles={cycles or chr(8734)}"
          f" out_dir={out_dir} mode={mode}"
          + (f" metrics_url={metrics_url}" if metrics_url else ""))

    def _health_check() -> bool:
        """v3.19: GET the metrics URL; return True if the server is reachable."""
        if not metrics_url:
            return True  # no health check configured
        try:
            req = _ur.Request(metrics_url, headers={"User-Agent": "charter-audit-loop"})
            with _ur.urlopen(req, timeout=5) as r:
                return r.status == 200
        except Exception:
            return False

    cycle = 0
    offline_skips = 0
    try:
        while True:
            # v3.19: health gate
            if not _health_check():
                offline_skips += 1
                print(f"[{cycle}] server offline ({metrics_url}), skipping cycle")
                if cycles and cycle + 1 >= cycles:
                    break
                _t.sleep(interval); cycle += 1
                continue
            ts = _t.strftime("%Y%m%d-%H%M%S")
            report = f"{out_dir}/gov_audit-{ts}.json"
            r = _sp.run(
                [_sys.executable, "-m", "charter.cli", "demo", "--gov",
                 "--trace-out", report],
                capture_output=True, text=True, timeout=120,
                cwd=_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
            if r.returncode != 0:
                print(f"[{cycle}] demo --gov failed (rc={r.returncode}): {r.stderr[:200]}")
                if cycles and cycle + 1 >= cycles:
                    break
                _t.sleep(interval); cycle += 1
                continue
            if dry_run:
                print(f"[{cycle}] dry-run: report written ({_os.path.basename(report)}), PR attach skipped")
            else:
                rc = attach_audit_to_pr(["--report", report, "----pr", str(pr)] + (["--repo", repo] if repo else []))
                status = "ok" if rc == 0 else f"rc={rc}"
                print(f"[{cycle}] audit posted ({status}) report={_os.path.basename(report)}")
            # v3.20: optional webhook delivery (Slack/Discord/Feishu)
            if webhook_url:
                # v3.21: process pending retries before new posts
                _n_retried = _webhook_process_retries()
                if _n_retried:
                    print(f"[{cycle}] webhook: retried {_n_retried} pending item(s)")
                import json as _json2
                with open(report, encoding="utf-8") as _rf:
                    report_doc = _json2.load(_rf)
                _summary = report_doc.get("summary", {})
                if webhook_template:
                    payload = _json2.loads(webhook_template)
                    payload.setdefault("text", f"charter audit cycle {cycle}")
                    payload["spans"] = _summary.get("spans")
                    payload["hallucinations"] = _summary.get("hallucinations")
                else:
                    payload = {"text": (f"Charter audit #{cycle}: spans={_summary.get('spans')} "
                                       f"halluc={_summary.get('hallucinations')} "
                                       f"avg_sim={_summary.get('avg_similarity')}")}
                wok, wmsg = _webhook_post(payload, webhook_url)
                if wok:
                    print(f"[{cycle}] webhook: ok ({wmsg})")
                else:
                    # v3.21: enqueue for retry with exponential backoff
                    import time as _t_retry
                    _webhook_enqueue_retry(payload, webhook_url, 1, delay_s=2.0)
                    print(f"[{cycle}] webhook: failed ({wmsg}), queued for retry")
            cycle += 1
            if cycles and cycle >= cycles:
                break
            _t.sleep(interval)
    except KeyboardInterrupt:
        print(f"\naudit-loop stopped after {cycle} cycles ({offline_skips} offline skips)")
        return 0
    print(f"audit-loop complete: {cycle} cycles, {offline_skips} offline skips")
    return 0


def validate_stress_report(argv: list) -> int:
    """v3.19: validate a CAS stress JSON report for schema completeness.

    v3.20: ``--ci`` flag outputs machine-readable JSON
    ``{"valid": bool, "errors": [...], "file": str}`` for GitHub Actions.

    Usage:
      python -m charter.cli validate-stress-report cas_report.json [--ci]
    """
    import json as _json

    REQUIRED_FIELDS = {
        "final": (int, float),
        "expected": int,
        "ok": bool,
        "conflicts": int,
        "ops": int,
        "conflict_rate": (float, int),
        "wall_s": (float, int),
        "n_writers": int,
        "iterations": int,
    }

    ci_mode = "--ci" in argv
    pos_args = [a for a in argv if a != "--ci"]

    if len(pos_args) != 1:
        print("usage: python -m charter.cli validate-stress-report <file.json> [--ci]")
        if ci_mode:
            print(_json.dumps({"valid": False, "errors": ["usage error"], "file": None}))
        return 2

    rpath = pos_args[0]
    import os as _os
    if not _os.path.isfile(rpath):
        err = f"file not found: {rpath}"
        print(err)
        if ci_mode:
            print(_json.dumps({"valid": False, "errors": [err], "file": rpath}))
        return 1

    try:
        doc = _json.load(open(rpath, encoding="utf-8"))
    except Exception as e:
        err = f"invalid JSON: {e}"
        print(err)
        if ci_mode:
            print(_json.dumps({"valid": False, "errors": [err], "file": rpath}))
        return 1

    if not isinstance(doc, dict):
        err = "report must be a JSON object"
        print(err)
        if ci_mode:
            print(_json.dumps({"valid": False, "errors": [err], "file": rpath}))
        return 1

    errors = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in doc:
            errors.append(f"missing field: {field}")
        else:
            val = doc[field]
            if expected_type is int and isinstance(val, bool):
                errors.append(f"field {field} must be int, got bool")
            elif expected_type is bool and not isinstance(val, bool):
                errors.append(f"field {field} must be bool, got {type(val).__name__}")
            elif expected_type is (float, int) and not isinstance(val, (int, float)):
                errors.append(f"field {field} must be numeric, got {type(val).__name__}")

    if ci_mode:
        result = {"valid": len(errors) == 0, "errors": errors, "file": rpath,
                  "fields_checked": len(REQUIRED_FIELDS)}
        print(_json.dumps(result, indent=2))
        return 0 if not errors else 1

    if errors:
        print(f"validation FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"validation OK: {len(REQUIRED_FIELDS)} required fields present in {rpath}")
    return 0

def _demo_governance_live() -> dict:
    """v3.15: REAL cross-process L3 demo.

    Spins up a reference HTTP KV gateway (thread-hosted, in-process), then
    launches TWO separate Python subprocesses:
      - writer:  node A writes a versioned value through its SemanticCache L3
      - reader:  node B (fresh process, no shared memory) reads it back via L3
    This proves distributed cache consistency across real process boundaries,
    not just within one process.
    """
    import os as _os
    import subprocess
    import sys as _sys

    from charter import reference_kv_gateway
    srv, url, _store = reference_kv_gateway()

    base_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    writer_script = (
        "import sys\n"
        f"sys.path.insert(0, {base_dir!r})\n"
        "from charter import SemanticCache, make_remote_backend\n"
        f"remote = make_remote_backend('http', {url!r}, timeout_s=3.0)\n"
        "c = SemanticCache(max_entries=8, remote=remote, ttl_s=300.0)\n"
        "c.put('market-size-2024', 500e9)\n"
        "print('writer version:', c.get_version('market-size-2024'))\n"
        "c.close()\n"
    )
    reader_script = (
        "import sys\n"
        f"sys.path.insert(0, {base_dir!r})\n"
        "from charter import SemanticCache, make_remote_backend\n"
        f"remote = make_remote_backend('http', {url!r}, timeout_s=3.0)\n"
        "c = SemanticCache(max_entries=8, remote=remote, ttl_s=300.0)\n"
        "val = c.get('market-size-2024')\n"
        "print('reader value:', val, 'version:', c.get_version('market-size-2024'),\n"
        "      'hits:', c.hits, 'misses:', c.misses)\n"
        "c.close()\n"
    )
    py = _sys.executable
    wr = subprocess.run([py, "-c", writer_script],
                        capture_output=True, text=True, timeout=60, cwd=base_dir)
    rd = subprocess.run([py, "-c", reader_script],
                        capture_output=True, text=True, timeout=60, cwd=base_dir)
    srv.shutdown()
    return {
        "gateway_url": url,
        "writer_out": wr.stdout.strip(),
        "reader_out": rd.stdout.strip(),
        "writer_exit": wr.returncode,
        "reader_exit": rd.returncode,
        "writer_stderr": wr.stderr.strip()[-200:] if wr.returncode else "",
        "reader_stderr": rd.stderr.strip()[-200:] if rd.returncode else "",
        "cross_process_l3_hit": rd.returncode == 0 and "hits: 1" in rd.stdout,
    }


if __name__ == "__main__":
    raise SystemExit(main())
    main()
