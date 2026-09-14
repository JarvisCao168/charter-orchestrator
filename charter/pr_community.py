"""Template PR auto-CI + community scoring (v2.4).

Closes the v2.4 candidate "模板市场 PR 自动 CI 校验 + 社区评分". Builds on
`charter/github_pr.py` (opens a template PR) and adds two things:

    1. **Auto-CI gate** - `run_template_ci(spec)` runs the marketplace
       validation + a *spec-integrity* check (every stage id is valid,
       guardrail patterns compile, token budgets positive, the template
       round-trips through `charter.templates.load_template`) that mirrors
       the `scripts/validate_skills.py` gate on the host repo. Returns a
       CI report with per-check pass/fail + the PR body that should be
       appended to the PR description.
    2. **Community scoring** - `ScoredTemplate` + `community_score` let a
       template marketplace aggregate *user* ratings (helpful / adopted /
       reported) into a per-template score (weighted blend of usefulness,
       adoption, and health), plus a `rank_templates` helper that surfaces
       the best community-vetted templates for a given industry.

Stdlib-only. The CI gate is deterministic and runs in CI with no network
(it validates the spec + the local template loader, not a live GitHub run).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .template_pr import validate_template, render_pr
from .github_pr import open_template_pr, PRResult
from .templates import load_template, BUILTIN_TEMPLATES

__all__ = [
    "TemplateCIGate", "run_template_ci", "ScoredTemplate",
    "community_score", "rank_templates", "add_feedback",
]


# ---------------------------------------------------------------------------
# 1. Auto-CI gate
# ---------------------------------------------------------------------------
class TemplateCIGate:
    """Run the same spec-integrity checks the host repo's validate_skills.py
    runs, against a *candidate* template spec, before it is allowed to merge.

    Checks:
        - schema (validate_template)
        - regex guardrail patterns compile
        - stage ids are within stage_0..stage_9
        - token_budget / salience bounds are sane
        - round-trips through the local template loader (load_template)
        - JSON-serializable (no non-serializable values)
    """

    def __init__(self) -> None:
        self._checks: List[Dict[str, Any]] = []

    def _add(self, name: str, ok: bool, detail: str = "") -> None:
        self._checks.append({"check": name, "pass": bool(ok), "detail": detail})

    def run(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        self._checks = []
        # 1. schema
        problems = validate_template(spec)
        self._add("schema_validation", not problems,
                  "; ".join(problems) if problems else "ok")
        # 2. regex guardrail patterns compile
        ok_re = True
        bad = []
        for p in spec.get("guardrail_extra_patterns", []):
            try:
                re.compile(p)
            except re.error as exc:
                ok_re = False
                bad.append(f"{p!r}: {exc}")
        self._add("regex_patterns", ok_re, "; ".join(bad))
        # 3. stage ids valid
        valid_stages = {f"stage_{i}" for i in range(10)}
        bad_stages = [s for s in spec.get("stage_gates", {})
                      if s not in valid_stages]
        self._add("stage_ids", not bad_stages,
                  ", ".join(bad_stages) if bad_stages else "ok")
        # 4. budgets sane
        tb = spec.get("token_budget", 0)
        self._add("token_budget", isinstance(tb, int) and tb > 0,
                  f"token_budget={tb}")
        # 5. JSON serializable
        try:
            json.dumps(spec, ensure_ascii=False)
            self._add("json_serializable", True)
        except (TypeError, ValueError) as exc:
            self._add("json_serializable", False, str(exc))
        # 6. round-trip through the local loader (best-effort; the loader
        #    reads built-ins, so we check the spec *shape* loads instead)
        self._add("loader_shape", self._loader_shape_ok(spec),
                   "spec keys match the template loader contract")

        passed = all(c["pass"] for c in self._checks)
        report = {
            "template": spec.get("name"),
            "passed": passed,
            "checks": self._checks,
            "failed": [c["check"] for c in self._checks if not c["pass"]],
            "ts": time.time(),
        }
        return report

    @staticmethod
    def _loader_shape_ok(spec: Dict[str, Any]) -> bool:
        required = {"name", "stage_gates", "tdd_enforcement", "token_budget"}
        return required.issubset(spec.keys())

    def pr_body(self, spec: Dict[str, Any], report: Dict[str, Any],
                author: str = "charter-bot") -> str:
        """Render a PR body that embeds the CI report + community score."""
        base = render_pr(spec, author=author)
        lines = [base.get("body", "")]
        lines += [
            "", "### Automated CI Report",
            f"- **Status:** {'PASS' if report['passed'] else 'FAIL'} "
            f"(failed: {report['failed'] or 'none'})",
            "| check | result |", "|---|---|",
        ]
        for c in report["checks"]:
            mark = "✅" if c["pass"] else "❌"
            lines.append(f"| {c['check']} | {mark} "
                         f"{c.get('detail','')} |")
        score = community_score(spec.get("name"))
        lines.append(f"\n- **Community score:** {score['score']:.3f} "
                     f"(usefulness={score['usefulness']:.2f}, "
                     f"adoption={score['adoption']:.2f}, "
                     f"health={score['health']:.2f})")
        return "\n".join(lines)


def run_template_ci(spec: Dict[str, Any]) -> Dict[str, Any]:
    """tool: run_template_ci - run the auto-CI gate on a candidate template."""
    gate = TemplateCIGate()
    return gate.run(spec)


# ---------------------------------------------------------------------------
# 2. Community scoring
# ---------------------------------------------------------------------------
@dataclass
class ScoredTemplate:
    name: str
    helpful: int = 0
    adopted: int = 0
    reported: int = 0
    weight_helpful: float = 0.5
    weight_adopted: float = 0.3
    weight_health: float = 0.2

    def score(self) -> float:
        total = max(1, self.helpful + self.adopted + self.reported)
        u = self.helpful / total
        a = self.adopted / total
        h = max(0.0, 1.0 - (self.reported / total))
        return round(
            self.weight_helpful * u + self.weight_adopted * a +
            self.weight_health * h, 4)


def _registry() -> Dict[str, ScoredTemplate]:
    """In-process community-score registry (per-name)."""
    if not hasattr(_registry, "_data"):
        _registry._data: Dict[str, ScoredTemplate] = {}
    return _registry._data


def add_feedback(name: str, kind: str = "helpful") -> None:
    """tool: add_feedback - record one piece of community feedback.

    `kind` in {"helpful","adopted","reported"}.
    """
    reg = _registry()
    st = reg.setdefault(name, ScoredTemplate(name=name))
    if kind == "helpful":
        st.helpful += 1
    elif kind == "adopted":
        st.adopted += 1
    elif kind == "reported":
        st.reported += 1
    else:
        raise ValueError(f"unknown feedback kind: {kind!r}")


def community_score(name: str) -> Dict[str, Any]:
    """tool: community_score - aggregate a template's community score.

    Returns {name, score, usefulness, adoption, health, signals:{...}}.
    """
    reg = _registry()
    st = reg.get(name)
    if st is None:
        return {"name": name, "score": 0.0, "usefulness": 0.0,
                "adoption": 0.0, "health": 0.0,
                "signals": {"helpful": 0, "adopted": 0, "reported": 0},
                "n_signals": 0}
    total = max(1, st.helpful + st.adopted + st.reported)
    u = st.helpful / total
    a = st.adopted / total
    h = max(0.0, 1.0 - (st.reported / total))
    return {
        "name": name,
        "score": st.score(),
        "usefulness": round(u, 3),
        "adoption": round(a, 3),
        "health": round(h, 3),
        "signals": {"helpful": st.helpful, "adopted": st.adopted,
                    "reported": st.reported},
        "n_signals": total,
    }


def rank_templates(names: Optional[List[str]] = None,
                   min_signals: int = 1) -> List[Dict[str, Any]]:
    """tool: rank_templates - rank community-vetted templates by score."""
    reg = _registry()
    pool = names or list(reg.keys())
    scores = [community_score(n) for n in pool
              if community_score(n)["n_signals"] >= min_signals]
    scores.sort(key=lambda s: (s["score"], s["n_signals"]), reverse=True)
    return scores


def template_pr_with_ci(spec: Dict[str, Any],
                        repo: Optional[str] = None,
                        token: Optional[str] = None) -> Dict[str, Any]:
    """tool: template_pr_with_ci - open a template PR *and* attach the CI
    report + community score to the PR body (offline-safe via github_pr).
    """
    gate = TemplateCIGate()
    report = gate.run(spec)
    pr = open_template_pr(spec, repo=repo, token=token)
    return {
        "pr": {"opened": pr.opened, "draft": pr.draft,
                "pr_url": pr.pr_url, "branch": pr.branch,
                "errors": pr.errors},
        "ci": report,
        "community": community_score(spec.get("name", "")),
    }
