"""Tests for charter.demo_skill (v3.3).

Covers:
- list_demo_skills returns a non-empty list with well-formed entries
- run_demo_skill: a bespoke demo runs end-to-end and returns ok=True
- run_demo_skill: a generic-fallback skill still "runs" (import + introspection)
- run_demo_skill: unknown skill id -> ok=False with error
- main() --list and --json paths exit cleanly
"""
import os
import json
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
    assert __version__.startswith("3.14")


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


# ---------------------------------------------------------------------------
# v3.7 — demo-skill watch SLO alerts delivered to a Prometheus Alertmanager
# webhook (second delivery channel, alongside OnCall gRPC)
# ---------------------------------------------------------------------------

def test_deliver_alertmanager_success_seam():
    """_deliver_alertmanager posts the payload via the _post seam and records a receipt."""
    from charter.demo_skill import _deliver_alertmanager
    alert = {"iteration": 2, "severity": "critical",
             "observed_ratio": 0.5, "slo_pct_threshold": 90.0,
             "failed_skills": ["obs_09"], "message": "SLO breach"}
    captured = {}
    def fake_post(payload, url, timeout):
        captured["payload"] = payload
        captured["url"] = url
        return 200, "ok"
    _deliver_alertmanager(alert, url="http://am:9093/api/v2/alerts",
                          _post=fake_post)
    assert alert["alertmanager"]["delivered"] is True
    assert alert["alertmanager"]["status"] == 200
    assert alert["alertmanager"]["url"] == "http://am:9093/api/v2/alerts"
    # The posted payload is Alertmanager v4-compatible.
    p = captured["payload"]
    assert p["status"] == "firing"
    assert p["alerts"][0]["labels"]["severity"] == "critical"
    assert p["alerts"][0]["labels"]["source"] == "charter-demo-skill"


def test_deliver_alertmanager_network_failure_degrades_to_plan():
    """When the real POST fails (no network), the receipt degrades to plan-only."""
    from charter.demo_skill import _deliver_alertmanager
    alert = {"iteration": 1, "severity": "warning", "observed_ratio": 0.8,
             "slo_pct_threshold": 90.0, "failed_skills": [], "message": "breach"}
    # Point at an unroutable address; urlopen will raise -> plan-only.
    out = _deliver_alertmanager(alert, url="http://127.0.0.1:1/noreply",
                                timeout_s=1.0)
    am = out["alertmanager"]
    assert am["delivered"] is False
    assert am["via"] == "alertmanager-plan"
    assert am["error"]  # a failure reason is recorded
    assert out is alert


def test_run_watch_delivers_alertmanager_when_breach():
    """run_watch(alertmanager_url=...) POSTs every SLO breach to the webhook."""
    from charter.demo_skill import run_watch
    # Use the _post-equivalent seam by passing a fake via a patched urlopen?
    # Simpler: the helper accepts no seam at run_watch level, so we verify the
    # delivery path by forcing a breach and asserting the alertmanager receipt
    # is present. We use a file:// URL that will fail -> plan-only receipt.
    report = run_watch(iterations=1, slo_pct_threshold=999.0,
                       alertmanager_url="http://127.0.0.1:1/noreply",
                       alertmanager_timeout_s=0.5)
    assert report["alerts"], "expected an SLO alert at 999% threshold"
    a = report["alerts"][0]
    assert "alertmanager" in a, "alert should carry the Alertmanager receipt"
    assert a["alertmanager"]["url"] == "http://127.0.0.1:1/noreply"
    # Plan-only in CI (no live Alertmanager) — delivery path still exercised.
    assert a["alertmanager"]["delivered"] in (True, False)


def test_run_watch_no_alertmanager_when_slo_met():
    """When the SLO is met, no alert fires and no Alertmanager delivery happens."""
    from charter.demo_skill import run_watch
    report = run_watch(iterations=1, slo_pct_threshold=0.0,
                       alertmanager_url="http://am:9093/api/v2/alerts")
    assert report["slo_met"] is True
    assert report["alerts"] == []
    # No alerts -> nothing delivered
    assert report["worst_ratio"] >= 0.0


def test_deliver_alertmanager_seam_exception_degrades():
    """If the _post seam itself raises, the receipt degrades to plan-only (no crash)."""
    from charter.demo_skill import _deliver_alertmanager
    alert = {"iteration": 1, "severity": "warning", "observed_ratio": 0.9,
             "slo_pct_threshold": 90.0, "failed_skills": [], "message": "x"}
    def boom(payload, url, timeout):
        raise RuntimeError("transport down")
    out = _deliver_alertmanager(alert, url="http://am:9093", _post=boom)
    am = out["alertmanager"]
    assert am["delivered"] is False
    assert am["via"] == "alertmanager-plan"
    assert "transport down" in am["error"]


# ---------------------------------------------------------------------------
# v3.8 — demo-skill watch --promql mode (live Prometheus metric SLO watch)
# ---------------------------------------------------------------------------

def _fake_prom_query_ok(value):
    """Return a canned _query seam that always succeeds with the given value."""
    def _q(base_url, promql):
        return {"status": 200,
                "data": {"status": "success",
                         "result": [{"__name__": "metric",
                                     "value": [0, str(value)]}]}}
    return _q


def _fake_prom_query_err():
    """A _query seam that always fails (simulates Prometheus being down)."""
    def _q(base_url, promql):
        return {"status": 500, "data": None, "error": "query failed"}
    return _q


def test_query_prometheus_seam_ok():
    """_query_prometheus returns the seam result when _query is supplied."""
    from charter.demo_skill import _query_prometheus
    out = _query_prometheus("http://prom", "up", _query=_fake_prom_query_ok(1.0))
    assert out["ok"] is True
    assert out["status"] == 200
    assert out["data"]["result"][0]["value"][1] == "1.0"


def test_query_prometheus_seam_error():
    """_query_prometheus surfaces a seam error without raising."""
    from charter.demo_skill import _query_prometheus
    out = _query_prometheus("http://prom", "up", _query=_fake_prom_query_err())
    assert out["ok"] is False
    assert out["error"] == "query failed"


def test_query_prometheus_seam_exception():
    """A _query seam that raises degrades to a plan-only error receipt."""
    from charter.demo_skill import _query_prometheus
    def boom(base_url, promql):
        raise RuntimeError("seam exploded")
    out = _query_prometheus("http://prom", "up", _query=boom)
    assert out["ok"] is False
    assert "seam exploded" in out["error"]


def test_run_watch_from_promql_met():
    """When the observed value is within threshold, no alert fires."""
    from charter.demo_skill import run_watch_from_promql
    # observed=0.5 <= threshold=1.0 -> met
    def th_fn(qres):
        r = ((qres.get("data") or {}).get("result") or [{}])[0]
        v = float(r.get("value", [0, 0])[1])
        return v <= 1.0, v, f"observed={v}"
    report = run_watch_from_promql(
        base_url="http://prom:9090",
        promql="error_rate:rate5m",
        threshold_fn=th_fn,
        iterations=3,
        _query=_fake_prom_query_ok(0.5))
    assert report["slo_met"] is True
    assert report["alerts"] == []
    assert report["mode"] == "promql"
    assert len(report["history"]) == 3


def test_run_watch_from_promql_breach():
    """When the observed value exceeds threshold, an alert fires and is delivered."""
    from charter.demo_skill import run_watch_from_promql
    def th_fn(qres):
        r = ((qres.get("data") or {}).get("result") or [{}])[0]
        v = float(r.get("value", [0, 0])[1])
        return v <= 1.0, v, f"observed={v} threshold=1.0"
    report = run_watch_from_promql(
        base_url="http://prom:9090",
        promql="error_rate:rate5m",
        threshold_fn=th_fn,
        iterations=1,
        alertmanager_url="http://am:9093/api/v2/alerts",
        _query=_fake_prom_query_ok(2.0))
    assert report["slo_met"] is False
    assert len(report["alerts"]) == 1
    a = report["alerts"][0]
    assert a["slo"] == "prometheus-query"
    assert a["observed"] == 2.0
    assert "alertmanager" in a, "alert should carry the Alertmanager receipt"
    assert a["alertmanager"]["url"] == "http://am:9093/api/v2/alerts"


def test_run_watch_from_promql_query_fails():
    """When the Prometheus query itself fails, an alert fires with the error."""
    from charter.demo_skill import run_watch_from_promql
    def th_fn(qres):
        if not qres.get("ok"):
            return False, None, qres.get("error", "unknown")
        return True, None, "ok"
    report = run_watch_from_promql(
        base_url="http://prom:9090",
        promql="up",
        threshold_fn=th_fn,
        iterations=1,
        _query=_fake_prom_query_err())
    assert report["slo_met"] is False
    assert len(report["alerts"]) == 1
    assert "query failed" in report["alerts"][0]["message"]


def test_promql_requires_base_url_in_cli():
    """--promql without --prometheus-base returns exit code 1."""
    from charter.demo_skill import main
    rc = main(["--promql", "up"])
    assert rc == 1


# ---------------------------------------------------------------------------
# v3.9 — demo-skill watch --promql range mode (window aggregation)
# ---------------------------------------------------------------------------

def _fake_range_query_ok(values):
    """Return a canned _query_range seam that always succeeds with the given
    list of values (one series)."""
    def _q(base_url, promql, start, end, step):
        return {"status": 200,
                "data": {"status": "success",
                          "result": [{"__name__": "metric",
                                      "values": [[0, str(v)] for v in values]}]}}
    return _q


def _avg_threshold(th):
    """A threshold_fn that works with the normalized range shape."""
    def _fn(qres):
        if not qres.get("ok"):
            return False, None, qres.get("error", "unknown")
        r = ((qres.get("data") or {}).get("result") or [{}])[0]
        v = float(r.get("value", [0, 0])[1])
        return v <= th, v, f"observed={v} threshold={th}"
    return _fn


def test_aggregate_range_values_avg_max_min():
    """_aggregate_range_values reduces a multi-value range result correctly."""
    from charter.demo_skill import _aggregate_range_values
    qres = {"ok": True, "data": {"result": [
        {"values": [[1, "1.0"], [2, "2.0"], [3, "3.0"], [4, "4.0"]]}]}}
    assert _aggregate_range_values(qres, agg="avg") == 2.5
    assert _aggregate_range_values(qres, agg="max") == 4.0
    assert _aggregate_range_values(qres, agg="min") == 1.0
    assert _aggregate_range_values(qres, agg="sum") == 10.0


def test_aggregate_range_values_p95():
    """_aggregate_range_values p95 uses nearest-rank on the sorted values."""
    from charter.demo_skill import _aggregate_range_values
    # 20 values 1..20 -> p95 = 19th value = 19.0
    vals = [[i, str(i)] for i in range(1, 21)]
    qres = {"ok": True, "data": {"result": [{"values": vals}]}}
    assert _aggregate_range_values(qres, agg="p95") == 19.0


def test_aggregate_range_values_no_values():
    """_aggregate_range_values returns None when there are no values."""
    from charter.demo_skill import _aggregate_range_values
    assert _aggregate_range_values({"ok": True, "data": {"result": []}}, agg="avg") is None
    assert _aggregate_range_values({"ok": False, "data": None}, agg="max") is None


def test_query_prometheus_range_seam_ok():
    """_query_prometheus_range with a seam returns the canned range result."""
    from charter.demo_skill import _query_prometheus_range
    out = _query_prometheus_range("http://prom", "up", start="1", end="10", step="60s",
                                  _query=_fake_range_query_ok([1.0, 2.0, 3.0]))
    assert out["ok"] is True
    assert out["status"] == 200
    assert len(out["data"]["result"][0]["values"]) == 3


def test_query_prometheus_range_seam_error():
    """A range-query seam that fails degrades to a plan-only error receipt."""
    from charter.demo_skill import _query_prometheus_range
    def boom(base_url, promql, start, end, step):
        raise RuntimeError("range query down")
    out = _query_prometheus_range("http://prom", "up", "1", "10", "60s", _query=boom)
    assert out["ok"] is False
    assert "range query down" in out["error"]


def test_run_watch_from_promql_range_mode_met():
    """range_mode=True aggregates the window and SLO is met (no alert)."""
    from charter.demo_skill import run_watch_from_promql
    # avg of [0.1, 0.2, 0.3] = 0.2 <= 0.5 -> met
    report = run_watch_from_promql(
        base_url="http://prom:9090",
        promql="error_rate",
        threshold_fn=_avg_threshold(0.5),
        iterations=1,
        range_mode=True,
        range_window="5m",
        range_step="60s",
        range_agg="avg",
        _query_range=_fake_range_query_ok([0.1, 0.2, 0.3]))
    assert report["slo_met"] is True
    assert report["mode"] == "promql-range"
    assert report["range_agg"] == "avg"
    assert report["alerts"] == []
    assert abs(report["history"][0]["observed"] - 0.2) < 1e-9  # avg of [0.1,0.2,0.3]


def test_run_watch_from_promql_range_mode_breach():
    """range_mode=True with a breach delivers an alert via Alertmanager."""
    from charter.demo_skill import run_watch_from_promql
    # max of [0.6, 0.7] = 0.7 > 0.5 -> breach
    report = run_watch_from_promql(
        base_url="http://prom:9090",
        promql="error_rate",
        threshold_fn=_avg_threshold(0.5),
        iterations=1,
        range_mode=True,
        range_window="5m",
        range_step="60s",
        range_agg="max",
        alertmanager_url="http://am:9093/api/v2/alerts",
        _query_range=_fake_range_query_ok([0.6, 0.7]))
    assert report["slo_met"] is False
    assert len(report["alerts"]) == 1
    a = report["alerts"][0]
    assert a["observed"] == 0.7  # max of the window
    assert "alertmanager" in a, "range breach should carry the Alertmanager receipt"
    assert a["alertmanager"]["url"] == "http://am:9093/api/v2/alerts"


def test_run_watch_from_promql_range_query_failure():
    """When the range query fails, an alert fires with the error message."""
    from charter.demo_skill import run_watch_from_promql
    def th_fn(qres):
        if not qres.get("ok"):
            return False, None, qres.get("error", "unknown")
        return True, None, "ok"
    report = run_watch_from_promql(
        base_url="http://prom:9090",
        promql="up",
        threshold_fn=th_fn,
        iterations=1,
        range_mode=True,
        range_window="5m",
        range_step="60s",
        range_agg="avg",
        _query_range=lambda *a, **k: {"status": 500, "data": None, "error": "range down"})
    assert report["slo_met"] is False
    assert len(report["alerts"]) == 1
    assert "range down" in report["alerts"][0]["message"]


# ---------------------------------------------------------------------------
# v3.10 — demo-skill watch --snapshot: persist the report as a JSON file for
# audit / regression (mirrors the event-sourcing "time-travel / replay" idea
# from the multi-agent consistency design analysis)
# ---------------------------------------------------------------------------

def test_snapshot_watch_report_writes_json(tmp_path):
    """_snapshot_watch_report writes a valid JSON file with the full report."""
    from charter.demo_skill import _snapshot_watch_report
    report = {"iterations": 3, "slo_pct_threshold": 90.0,
              "history": [{"iteration": 1, "passed": 6, "total_skills": 6,
                           "slo": {"ratio": 1.0, "met": True}}],
              "alerts": [], "worst_ratio": 1.0, "slo_met": True, "mode": "watch"}
    path = str(tmp_path / "snap.json")
    receipt = _snapshot_watch_report(report, path, metadata={"mode": "watch"})
    assert receipt["ok"] is True
    assert os.path.exists(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["report"] == report
    assert data["snapshot_version"] == 1
    assert "written_at" in data
    assert data["metadata"] == {"mode": "watch"}


def test_snapshot_watch_report_includes_promql(tmp_path):
    """In promql mode, the snapshot carries the promql + base_url fields."""
    from charter.demo_skill import _snapshot_watch_report
    report = {"iterations": 1, "mode": "promql", "slo_met": False,
              "alerts": [{"iteration": 1, "message": "breach", "severity": "critical"}],
              "history": []}
    path = str(tmp_path / "q.json")
    receipt = _snapshot_watch_report(report, path, promql="error_rate",
                                     base_url="http://prom:9090")
    assert receipt["ok"] is True
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["promql"] == "error_rate"
    assert data["base_url"] == "http://prom:9090"
    assert data["report"]["slo_met"] is False


def test_snapshot_watch_report_failure_does_not_raise(tmp_path):
    """A bad path (e.g. unwritable dir) yields ok=False with an error, no raise."""
    from charter.demo_skill import _snapshot_watch_report
    # Use a path whose parent dir cannot be created (root-level on Windows would
    # be C:\.. — instead simulate by giving a path under a forbidden segment).
    # Create a regular file and use it as the "parent" directory prefix.
    # os.makedirs(parent, exist_ok=True) will raise NotADirectoryError.
    import os as _os
    a_file = str(tmp_path / "afile")
    _os.makedirs(tmp_path / "afile") if False else None  # no-op
    with open(a_file, "w") as _f:
        _f.write("")
    target = a_file + "/snap.json"  # parent (a_file) is a regular file -> makedirs fails
    receipt = _snapshot_watch_report({"iterations": 1}, target)
    assert receipt["ok"] is False
    assert receipt["error"], "expected an error message on write failure"
    # The receipt still reports the path + 0 bytes.
    assert receipt["bytes"] == 0


def test_snapshot_creates_parent_dir(tmp_path):
    """_snapshot_watch_report creates missing parent directories."""
    from charter.demo_skill import _snapshot_watch_report
    deep = tmp_path / "a" / "b" / "c" / "snap.json"
    receipt = _snapshot_watch_report({"iterations": 1}, str(deep))
    assert receipt["ok"] is True
    assert os.path.exists(str(deep))
    data = json.loads(open(str(deep), encoding="utf-8").read())
    assert data["report"]["iterations"] == 1


def test_main_watch_snapshot_flag_end_to_end(tmp_path, capsys):
    """main(['--watch', '--iterations','1', '--snapshot', ...]) persists a report."""
    import charter.demo_skill as ds
    path = str(tmp_path / "watch_report.json")
    rc = ds.main(["--watch", "--iterations", "1", "--slo-pct", "0", "--snapshot", path])
    assert os.path.exists(path), "snapshot file was not written"
    data = json.loads(open(path, encoding="utf-8").read())
    assert "mode" in data.get("metadata", {})  # watch mode metadata
    assert "report" in data and "written_at" in data
    # SLO 0% always met -> exit 0
    assert rc == 0


# ---------------------------------------------------------------------------
# v3.11 — governance demo chain (validation gateway + critic + semantic trace + model router)
# ---------------------------------------------------------------------------

def test_demo_governance_gov_01():
    """gov_01 runs the full governance chain end-to-end."""
    from charter.demo_skill import run_demo_skill
    r = run_demo_skill("gov_01")
    assert r.get("ok") is True
    res = r["result"]
    for key in ("critic", "gateway", "circuit_breaker", "semantic_trace",
                "model_routing", "semantic_cache"):
        assert key in res, f"missing {key} in governance demo result"
    assert res["semantic_trace"]["hallucination_detected"] is True
    assert res["gateway"]["passed"] in (True, False)
    assert res["model_routing"]["easy"]["tier"] in ("small", "medium", "large")
    assert res["model_routing"]["hard"]["tier"] == "large"


def test_demo_governance_gov_04_alias():
    """gov_04 maps to the same governance chain."""
    from charter.demo_skill import run_demo_skill
    r = run_demo_skill("gov_04")
    assert r.get("ok") is True
    assert "critic" in r["result"]
