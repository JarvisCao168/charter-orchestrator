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


def test_version_is_v3_4():
    assert __version__.startswith("3.4")


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
