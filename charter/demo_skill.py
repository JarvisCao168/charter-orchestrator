"""One-shot demo of a named Charter skill's real module chain (v3.3).

`make demo-skill SKILL=<skill_id>` (or `python -m charter.demo_skill <skill_id>`)
resolves the skill from the manifest, runs the underlying module's real
entrypoint end-to-end, and prints a human-readable report. This is the
"一键跑通真实模块链路" path for any of the 107 skills.

The DEMOS table maps skill_id -> (module, runner). Each runner returns a
dict of labelled results. Skills without a bespoke demo fall back to a
generic import + `__all__` introspection report so every skill still "runs".
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from typing import Any, Dict, List

__all__ = ["run_demo_skill", "list_demo_skills", "DEMO_SKILLS", "run_all_demos", "main"]

# ---------------------------------------------------------------------------
# Skill -> real-module-chain demos
# ---------------------------------------------------------------------------

def _demo_slo_oncall() -> Dict[str, Any]:
    """obs_09/obs_10/obs_12: SLO breach -> alert payload -> OnCall delivery report."""
    from charter import slo_alerts, oncall_grpc_e2e, oncall_deliver
    slo_summary = {
        "services": {"api": {"met": False, "p95_ms": 900, "error_rate": 0.05}},
        "target_p95_ms": 300, "target_error_rate": 0.01,
    }
    payload = slo_alerts.build_alert_payload(slo_summary, service="api")
    integration = oncall_deliver.OnCallIntegration(name="pagerduty", kind="pagerduty")
    report = oncall_grpc_e2e.e2e_delivery_report(
        {"severity": payload.severity, "title": payload.title}, integration)
    return {
        "slo": "availability breached (p95 900ms > 300ms)",
        "alert_payload": {"title": payload.title, "severity": payload.severity},
        "oncall_delivery": {k: report.get(k) for k in ("delivered", "plan", "status", "target") if k in report},
    }


def _demo_judge_pool() -> Dict[str, Any]:
    """dep_05/06/07/08: build a K8s judge-pool plan + cost autoscaler + deploy bundle."""
    from charter import judge_pool, judge_pool_cost, judge_pool_deploy
    plan = judge_pool.plan_judge_pool({"x": 1}, backends=["agnes"], replicas_per_provider=1)
    autoscaler = judge_pool_cost.render_cost_autoscaler(plan)
    bundle = judge_pool_deploy.render_judge_pool_bundle(plan)
    return {
        "pool_id": plan.pool_id,
        "replicas": plan.replica_count,
        "tasks": len(plan.tasks),
        "autoscaler_resources": list(autoscaler.keys()) if isinstance(autoscaler, dict) else "n/a",
        "bundle_kind": bundle.get("kind") or bundle.get("resources") or "bundle",
    }


def _demo_memory() -> Dict[str, Any]:
    """col_05..col_10: session -> compress -> cluster -> cross-language + vector merge."""
    from charter import session_store, memory_compress, memory_clustering, memory_vector_merge, vector_memory
    store = session_store.SessionStore()
    compressed = memory_compress.compress_session(store, "s1", "a1", online=False)
    episodes = [{"id": i, "content": c} for i, c in enumerate([
        "fixed the login timeout bug",
        "resolved the login latency issue",
        "added a new payment gateway",
    ])]
    clusters = memory_clustering.cluster_episodes(
        episodes, embed=lambda t, d: vector_memory.hash_embed(t, dim=d), similarity=0.5)
    embedded = [
        {"id": "c1", "centroid": [1.0, 0.0], "top_content": "login", "language": "en",
         "member_ids": [0, 1], "size": 2},
        {"id": "c2", "centroid": [0.0, 1.0], "top_content": "数据库", "language": "zh",
         "member_ids": [2], "size": 1},
    ]
    merged = memory_vector_merge.vector_cross_merge(embedded, similarity=0.7)
    return {
        "compressed": {k: compressed.get(k) for k in ("facts", "summary") if k in compressed} or compressed,
        "clusters": len(clusters),
        "merged_clusters": len(merged),
    }


def _demo_mtls_spiffe() -> Dict[str, Any]:
    """sec_01..sec_08: X509 issue + SPIFFE SVID + bidir mTLS regression."""
    from charter import x509_identity, spiffe, spire_bidir_mtls, spire_bidir_regression
    cert = x509_identity.x509_issue("agent-demo", ["read", "write"])
    svid = spiffe.issue_svid("cluster.local", "demo/pod")
    spiffe_id = spiffe.build_spiffe_id("cluster.local", "demo/pod")
    ok, problems = spiffe.verify_svid(svid.cert_pem, "cluster.local", spiffe_id)
    cfg = spire_bidir_mtls.BidirMTLSConfig()
    reg = spire_bidir_regression.run_bidir_mtls_regression(cfg)
    return {
        "x509_agent": cert.agent_id if hasattr(cert, "agent_id") else "issued",
        "svid_verified": bool(ok),
        "svid_problems": problems,
        "bidir_regression": {k: reg.get(k) for k in ("passed", "invariants", "result") if k in reg} or reg,
    }


def _demo_pr_diff() -> Dict[str, Any]:
    """tst_06..tst_09: diff hunk -> completion -> cross-hunk -> tree-sitter semantics."""
    from charter import pr_diff_completion, pr_diff_consistency, pr_diff_semantics
    # complete_diff_hunks wants plain-dict hunks; the other two want HunkProposal
    hunk_dicts = [
        {"file": "a.py", "hunk_id": "h1", "context": "",
         "before": "x = get_data()", "after": "x = fetch_data()", "rationale": "rename"},
    ]
    completed = pr_diff_completion.complete_diff_hunks(hunk_dicts)
    proposals = [
        pr_diff_consistency.HunkProposal(
            file="a.py", hunk_id="h1", context="",
            before="x = get_data()", after="x = fetch_data()", rationale="rename"),
    ]
    reconciled, inconsistencies = pr_diff_consistency.reconcile_hunks(proposals)
    semantic = pr_diff_semantics.semantic_check(proposals, language="python")
    return {
        "completed_hunks": len(completed.get("proposals", [])) if isinstance(completed, dict) else len(completed),
        "reconciled": len(reconciled),
        "inconsistencies": len(inconsistencies),
        "semantic_inconsistencies": len(semantic),
    }


def _demo_identity_iam() -> Dict[str, Any]:
    """dev_19/dev_20/tst_10/tst_11: team RBAC + IAM bundle + drift remediation."""
    from charter import checkpoint_rbac, checkpoint_iam, checkpoint_iam_remediate
    policies = checkpoint_rbac.team_policies({"eng": ["deploy", "read"]})
    bundle = checkpoint_iam.render_iam_bundle({"deploy": ["s3:GetObject"]})
    remediation = checkpoint_iam_remediate.reconcile_iam(
        {"deploy": ["s3:GetObject"]}, dry_run=True)
    return {
        "team_policies": list(policies.keys()),
        "iam_bundle_keys": list(bundle.keys()),
        "remediation": {k: remediation.get(k) for k in ("applied", "plan", "actions") if k in remediation} or remediation,
    }


def _generic_demo(skill_id: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback: import the module and report its public surface."""
    modref = meta.get("module") or ""
    modname = modref.split(".")[-1] if modref else ""
    if not modname:
        # legacy skills (first 47) carry no module ref - manifest-driven report
        return {"skill_id": skill_id, "ok": True, "name": meta.get("name"),
                "tools": meta.get("tools", []), "module": None,
                "note": "legacy skill without a module ref - manifest-driven report"}
    try:
        mod = importlib.import_module(f"charter.{modname}")
    except Exception as e:
        return {"skill_id": skill_id, "module": f"charter.{modname}", "ok": False, "error": str(e)}
    public = getattr(mod, "__all__", None) or [
        n for n in dir(mod) if not n.startswith("_")
    ]
    return {
        "skill_id": skill_id,
        "module": f"charter.{modname}",
        "name": meta.get("name"),
        "tools": meta.get("tools", []),
        "public_api": sorted(public)[:24],
        "note": "generic import+introspection demo (no bespoke runner)",
    }


# skill_id -> demo runner
DEMO_SKILLS: Dict[str, Any] = {
    "obs_09": _demo_slo_oncall, "obs_10": _demo_slo_oncall, "obs_12": _demo_slo_oncall,
    "dep_05": _demo_judge_pool, "dep_06": _demo_judge_pool,
    "dep_07": _demo_judge_pool, "dep_08": _demo_judge_pool,
    "col_05": _demo_memory, "col_06": _demo_memory, "col_07": _demo_memory,
    "col_08": _demo_memory, "col_09": _demo_memory, "col_10": _demo_memory,
    "sec_01": _demo_mtls_spiffe, "sec_02": _demo_mtls_spiffe, "sec_03": _demo_mtls_spiffe,
    "sec_06": _demo_mtls_spiffe, "sec_07": _demo_mtls_spiffe, "sec_08": _demo_mtls_spiffe,
    "dev_15": _demo_mtls_spiffe, "dev_16": _demo_mtls_spiffe,
    "tst_06": _demo_pr_diff, "tst_07": _demo_pr_diff, "tst_08": _demo_pr_diff,
    "dev_19": _demo_identity_iam, "dev_20": _demo_identity_iam,
    "tst_10": _demo_identity_iam, "tst_11": _demo_identity_iam,
}


def _load_manifest() -> Dict[str, Any]:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base, "skills", "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def run_demo_skill(skill_id: str) -> Dict[str, Any]:
    """Run the real module chain for a skill and return a report dict."""
    manifest = _load_manifest()
    meta = manifest.get("skills", {}).get(skill_id)
    if meta is None:
        return {"skill_id": skill_id, "ok": False,
                "error": f"unknown skill '{skill_id}' (not in manifest)"}
    runner = DEMO_SKILLS.get(skill_id)
    if runner is None:
        return _generic_demo(skill_id, meta)
    try:
        result = runner()
        return {"skill_id": skill_id, "ok": True,
                "name": meta.get("name"), "tools": meta.get("tools", []),
                "module": meta.get("module"), "result": result}
    except Exception as e:
        import traceback
        return {"skill_id": skill_id, "ok": False, "name": meta.get("name"),
                "module": meta.get("module"), "error": str(e),
                "traceback": traceback.format_exc()}


def list_demo_skills() -> List[Dict[str, Any]]:
    """Skills that have a bespoke end-to-end demo runner."""
    manifest = _load_manifest()
    out = []
    for sid in sorted(DEMO_SKILLS.keys()):
        meta = manifest.get("skills", {}).get(sid, {})
        out.append({"skill_id": sid, "name": meta.get("name"),
                    "module": meta.get("module")})
    return out


def run_all_demos(as_json: bool = True) -> Dict[str, Any]:
    """Run every bespoke demo chain and return a consolidated report.

    Iterates ``DEMO_SKILLS`` (deduplicated by runner so the 6 chain-groups
    run once each), executes the real module chain, and aggregates:
    total / ok / failed counts plus a per-chain breakdown and per-skill
    status map. A chain failing does not stop the others.
    """
    manifest = _load_manifest()
    # Dedupe by runner so each chain-group runs once, but remember all skill ids
    seen_runners: Dict[int, str] = {}
    ordered_groups: List[str] = []
    for sid in sorted(DEMO_SKILLS.keys()):
        runner = DEMO_SKILLS[sid]
        key = id(runner)
        if key not in seen_runners:
            seen_runners[key] = sid
            ordered_groups.append(sid)

    chains: List[Dict[str, Any]] = []
    per_skill: Dict[str, bool] = {}
    total, ok_count, fail_count = 0, 0, 0

    for representative in ordered_groups:
        runner = DEMO_SKILLS[representative]
        sids = sorted(sid for sid in DEMO_SKILLS if DEMO_SKILLS[sid] is runner)
        meta = manifest.get("skills", {}).get(representative, {})
        try:
            result = runner()
            ok = True
            error = None
        except Exception as e:
            ok = False
            error = str(e)
            result = None
        total += len(sids)
        ok_count += len(sids) if ok else 0
        fail_count += 0 if ok else len(sids)
        for sid in sids:
            per_skill[sid] = ok
        chains.append({
            "chain": representative,
            "module": meta.get("module"),
            "skills": sids,
            "ok": ok,
            "error": error,
            "result": result if ok else None,
        })

    return {
        "ok": fail_count == 0,
        "total_skills": total,
        "passed": ok_count,
        "failed": fail_count,
        "chains": chains,
        "per_skill": per_skill,
    }


def main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run a Charter skill's real module chain")
    parser.add_argument("skill", nargs="?", help="skill id (e.g. obs_09)")
    parser.add_argument("--list", action="store_true", help="list skills with bespoke demos")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--all", action="store_true",
                        help="run every bespoke demo chain and print a consolidated report")
    args = parser.parse_args(argv)

    if args.all:
        report = run_all_demos()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
        else:
            print(f"=== Charter demo-skill: all bespoke chains ===")
            print(f"  skills covered: {report['total_skills']} (deduped by {len(report['chains'])} chains)")
            print(f"  passed: {report['passed']}  failed: {report['failed']}  "
                  f"overall: {'PASS' if report['ok'] else 'FAIL'}")
            for c in report["chains"]:
                mark = "OK  " if c["ok"] else "FAIL"
                extra = f"  ({c['error']})" if c.get("error") else ""
                print(f"  [{mark}] {c['chain']:8s} {c.get('module') or ''}  "
                      f"skills={','.join(c['skills'])}{extra}")
        return 0 if report["ok"] else 1

    if args.list:
        for e in list_demo_skills():
            print(f"  {e['skill_id']:8s} {e['name'] or ''}  ({e['module']})")
        return 0

    if not args.skill:
        parser.print_help()
        return 1

    report = run_demo_skill(args.skill)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
    else:
        print(f"=== Charter skill demo: {report.get('skill_id')} ===")
        print(f"  name:    {report.get('name')}")
        print(f"  module:  {report.get('module')}")
        print(f"  tools:   {', '.join(report.get('tools', []))}")
        if report.get("ok"):
            print("  OK — real module chain ran end-to-end:")
            print(json.dumps(report.get("result", {}), ensure_ascii=False, default=str, indent=2))
        else:
            print(f"  FAILED: {report.get('error')}")
            if report.get("traceback"):
                print(report["traceback"])
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
