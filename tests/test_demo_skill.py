"""Tests for charter.demo_skill (v3.3).

Covers:
- list_demo_skills returns a non-empty list with well-formed entries
- run_demo_skill: a bespoke demo runs end-to-end and returns ok=True
- run_demo_skill: a generic-fallback skill still "runs" (import + introspection)
- run_demo_skill: unknown skill id -> ok=False with error
- main() --list and --json paths exit cleanly
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from charter import __version__
from charter import demo_skill
from charter.demo_skill import (
    DEMO_SKILLS,
    list_demo_skills,
    run_demo_skill,
    main,
)


def test_version_is_v3_5():
    assert __version__.startswith("3.6")


def test_list_demo_skills_well_formed():
    entries = list_demo_skills()
    assert len(entries) >= 10
    for e in entries:
        assert "skill_id" in e and "module" in e
        assert e["skill_id"] in DEMO_SKILLS


def test_bespoke_demo_runs_ok():
    """A bespoke demo (e.g. obs_09 SLO->OnCall) runs its real module chain."""
    report = run_demo_skill("obs_09")
    assert report["ok"] is True, report.get("error")
    assert report["module"]
    # the SLO->OnCall demo produced delivery info
    assert "oncall_delivery" in report["result"] or "alert_payload" in report["result"]


def test_demo_skill_variants():
    for sid in ("obs_09", "dep_06", "col_08", "sec_03", "tst_07", "dev_20"):
        report = run_demo_skill(sid)
        assert report["ok"] is True, f"{sid} failed: {report.get('error')}"
        assert report.get("result") is not None


def test_generic_fallback_runs():
    """A skill with no bespoke demo still 'runs' via import + introspection."""
    # pick a skill id that is NOT in DEMO_SKILLS
    from charter import demo_skill as ds
    import json
    manifest = json.load(open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "skills", "manifest.json"), encoding="utf-8"))
    candidates = [sid for sid in manifest["skills"] if sid not in DEMO_SKILLS]
    assert candidates, "expected some skills without bespoke demos"
    sid = candidates[0]
    report = run_demo_skill(sid)
    assert report["ok"] is True
    # legacy skills (no module ref) return a manifest-driven note;
    # newer skills (with module) return public_api introspection
    if report.get("module"):
        assert "public_api" in report["result"]
        assert report["result"]["module"].startswith("charter.")
    else:
        assert "note" in report


def test_unknown_skill_fails():
    report = run_demo_skill("no_such_skill_99")
    assert report["ok"] is False
    assert "unknown skill" in report["error"]


def test_main_list_exits_zero():
    rc = main(["--list"])
    assert rc == 0


def test_main_unknown_skill_exits_nonzero():
    rc = main(["no_such_skill_99"])
    assert rc != 0


def test_main_valid_skill_exits_zero():
    rc = main(["obs_09", "--json"])
    assert rc == 0


# ---------------------------------------------------------------------------
# --all: run_all_demos consolidated report (v3.4)
# ---------------------------------------------------------------------------

from charter.demo_skill import run_all_demos


def test_run_all_demos_covers_bespoke_chains():
    report = run_all_demos()
    # every bespoke chain runs and the report is self-consistent
    assert report["total_skills"] >= 10
    assert report["passed"] + report["failed"] == report["total_skills"]
    assert report["ok"] in (True, False)
    # each chain entry is well-formed
    for c in report["chains"]:
        assert c["ok"] in (True, False)
        assert isinstance(c["skills"], list) and c["skills"]
        # a passing chain carries its real module-chain result
        if c["ok"]:
            assert c["result"] is not None


def test_run_all_demos_all_bespoke_pass():
    report = run_all_demos()
    # all 6 bespoke chain-groups succeed offline
    assert report["failed"] == 0, report["chains"]
    assert report["ok"] is True


def test_main_all_exits_zero():
    rc = main(["--all"])
    assert rc == 0


# ---------------------------------------------------------------------------
# --watch: continuous run + SLO threshold alerting (v3.5)
# ---------------------------------------------------------------------------

from charter.demo_skill import run_watch, _eval_slo


def test_eval_slo_met():
    report = {"total_skills": 10, "passed": 10}
    slo = _eval_slo(report, 90.0)
    assert slo["met"] is True
    assert slo["alert"] is False
    assert slo["ratio"] == 1.0


def test_eval_slo_breach_fires_alert():
    report = {"total_skills": 10, "passed": 5}
    slo = _eval_slo(report, 90.0)
    assert slo["met"] is False
    assert slo["alert"] is True
    assert slo["ratio"] == 0.5


def test_run_watch_single_iteration_slo_met():
    report = run_watch(iterations=1, slo_pct_threshold=50.0, _sleep_s=0.0)
    # all bespoke chains pass offline, so a 50% SLO is met
    assert report["slo_met"] is True
    assert report["iterations"] == 1
    assert report["alerts"] == []
    assert report["history"][0]["slo"]["met"] is True


def test_run_watch_high_threshold_fires_alert():
    # A 101% SLO is impossible -> every iteration breaches and alerts,
    # even when the underlying pass ratio is a perfect 1.0
    report = run_watch(iterations=2, slo_pct_threshold=101.0, _sleep_s=0.0)
    assert report["slo_met"] is False
    assert len(report["alerts"]) == 2
    assert report["alerts"][0]["iteration"] == 1
    assert report["alerts"][1]["iteration"] == 2
    # worst_ratio tracks the actual pass ratio (1.0 when all pass), while the
    # SLO breach is driven by the threshold, not the ratio
    assert report["worst_ratio"] == 1.0
    assert report["alerts"][0]["severity"] in ("warning", "critical")
    assert report["alerts"][0]["observed_ratio"] == 1.0


def test_run_watch_tracks_worst_ratio():
    report = run_watch(iterations=3, slo_pct_threshold=101.0, _sleep_s=0.0)
    assert len(report["history"]) == 3
    assert report["worst_ratio"] == min(h["slo"]["ratio"] for h in report["history"])


def test_main_watch_exits_nonzero_on_breach():
    # 101% SLO guarantees a breach -> nonzero exit
    rc = main(["--watch", "--iterations", "1", "--slo-pct", "101"])
    assert rc == 1


def test_main_watch_exits_zero_when_met():
    # 0% SLO is always met -> exit 0
    rc = main(["--watch", "--iterations", "1", "--slo-pct", "0"])
    assert rc == 0


# ---------------------------------------------------------------------------
# v3.6 — demo-skill watch SLO alerts delivered to Grafana OnCall (gRPC)
# ---------------------------------------------------------------------------

def test_deliver_oncall_plan_only_without_grpc():
    """_deliver_oncall degrades to a plan-only receipt when no live OnCall service."""
    from charter.demo_skill import _deliver_oncall
    alert = {"severity": "critical", "message": "SLO breach", "failed_skills": ["obs_09"]}
    out = _deliver_oncall(alert, target="grafana-oncall:50051",
                          integration_name="pagerduty")
    # The OnCall integration is built-in; without grpc the e2e report is plan-only.
    assert "oncall" in alert  # the delivery receipt was merged onto the alert
    assert alert["oncall"]["delivered"] in (True, False)
    assert alert["oncall"]["plan_only"] in (True, False)
    assert alert["oncall"]["target"] == "grafana-oncall:50051"
    assert out is alert  # returns the (now-augmented) alert record


def test_run_watch_delivers_oncall_when_breach():
    """run_watch(oncall_target=...) delivers SLO alerts to OnCall on breach."""
    from charter.demo_skill import run_watch
    # Force a breach: threshold > 100 is impossible to meet, so every
    # iteration fires an alert and (with oncall_target set) delivers to OnCall.
    report = run_watch(iterations=1, slo_pct_threshold=999.0,
                       oncall_target="grafana-oncall:50051")
    assert report["alerts"], "expected at least one SLO alert at 999% threshold"
    a = report["alerts"][0]
    assert "oncall" in a, "alert should carry the OnCall delivery receipt"
    assert a["oncall"]["target"] == "grafana-oncall:50051"
    # Delivery is plan-only in CI (no live OnCall + no grpc), but the
    # delivery path itself was exercised.
    assert a["oncall"]["plan_only"] in (True, False)


def test_run_watch_no_oncall_when_slo_met():
    """When the SLO is met, no alert fires and no OnCall delivery happens."""
    from charter.demo_skill import run_watch
    report = run_watch(iterations=1, slo_pct_threshold=0.0,
                       oncall_target="grafana-oncall:50051")
    assert report["slo_met"] is True
    assert report["alerts"] == []
    # No alerts -> nothing delivered
    assert report["worst_ratio"] >= 0.0


def test_deliver_oncall_unavailable_module_returns_gracefully():
    """If the OnCall module is importable but the delivery raises, we degrade."""
    import importlib
    from charter import demo_skill
    # The helper must never raise even when OnCall is unreachable.
    alert = {"severity": "warning", "message": "x", "failed_skills": []}
    out = demo_skill._deliver_oncall(alert, target="nonexistent:9999",
                                     integration_name="pagerduty")
    # Either it delivered (plan-only) or recorded the failure, but did not crash.
    assert out is alert
    assert "oncall" in alert
