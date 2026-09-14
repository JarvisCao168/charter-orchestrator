"""Industry SOP template marketplace - PR flow (v2.1).

Lets a community member *propose* a new industry template and have it merged
through a review gate instead of just dropping a file. This is the "marketplace
PR flow" upgrade to `charter/templates.py`:

    1. `propose_template(spec)` - validate a candidate template against the
       marketplace schema (required keys, valid stage ids, known rule fields).
    2. `TemplatePR` - a reviewable change object with author, diff, and gates.
    3. `merge(pr)` - run marketplace governance (schema re-check + a
       confirm_gate-style human sign-off) and register into the loadable set.

Validation rules:
    - name must be a slug
    - stage_gates keys must be stage_0..stage_9
    - tdd_enforcement in {off, soft, strict}
    - token_budget positive int
    - guardrail_extra_patterns must be valid regex
    - audit_required_stages subset of stage_0..stage_9

No external deps; the "merge" is in-memory (a real marketplace would POST the
JSON to the repo + open a PR; see `render_pr()` for that body).
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

VALID_STAGES = {f"stage_{i}" for i in range(10)}
VALID_TDD = {"off", "soft", "strict"}


class TemplateSpecError(ValueError):
    pass


def _valid_regex(pattern: str) -> bool:
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False


def validate_template(spec: Dict[str, Any]) -> List[str]:
    """Return a list of problems (empty = valid)."""
    problems: List[str] = []
    name = spec.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]+", name):
        problems.append(f"name must be a slug [a-z0-9-], got {name!r}")
    if not spec.get("label"):
        problems.append("label is required")
    for stage, checks in (spec.get("stage_gates") or {}).items():
        if stage not in VALID_STAGES:
            problems.append(f"unknown stage {stage!r} in stage_gates")
        if not isinstance(checks, list):
            problems.append(f"stage_gates[{stage}] must be a list of checks")
    tdd = spec.get("tdd_enforcement", "soft")
    if tdd not in VALID_TDD:
        problems.append(f"tdd_enforcement {tdd!r} not in {VALID_TDD}")
    budget = spec.get("token_budget")
    if budget is not None and (not isinstance(budget, int) or budget <= 0):
        problems.append("token_budget must be a positive int")
    for pat in (spec.get("guardrail_extra_patterns") or []):
        if not _valid_regex(pat):
            problems.append(f"invalid guardrail regex {pat!r}")
    for st in (spec.get("audit_required_stages") or []):
        if st not in VALID_STAGES:
            problems.append(f"unknown stage {st!r} in audit_required_stages")
    return problems


@dataclass
class TemplatePR:
    pr_id: str
    author: str
    spec: Dict[str, Any]
    created_ts: float = field(default_factory=time.time)
    status: str = "open"          # open | approved | merged | rejected
    approvers: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        self.problems = validate_template(self.spec)
        return self.problems

    def approve(self, reviewer: str) -> None:
        if self.problems and not self.approvers:
            # first review must re-validate
            self.validate()
        if self.problems:
            raise TemplateSpecError(
                f"cannot approve with open problems: {self.problems}")
        if reviewer not in self.approvers:
            self.approvers.append(reviewer)

    def can_merge(self, min_approvers: int = 1) -> bool:
        return (self.status != "merged"
                and not self.problems
                and len(self.approvers) >= min_approvers)


class TemplateMarketplace:
    """In-memory registry of merged templates + open PRs."""

    def __init__(self, builtin: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        from .templates import BUILTIN_TEMPLATES
        self.merged: Dict[str, Dict[str, Any]] = dict(builtin or BUILTIN_TEMPLATES)
        self.open_prs: Dict[str, TemplatePR] = {}

    def propose(self, spec: Dict[str, Any], author: str) -> TemplatePR:
        pr = TemplatePR(pr_id="tplpr_" + uuid.uuid4().hex[:10],
                        author=author, spec=dict(spec))
        pr.validate()
        self.open_prs[pr.pr_id] = pr
        return pr

    def approve(self, pr_id: str, reviewer: str) -> None:
        self.open_prs[pr_id].approve(reviewer)

    def merge(self, pr_id: str, min_approvers: int = 1) -> str:
        pr = self.open_prs[pr_id]
        if not pr.can_merge(min_approvers):
            raise TemplateSpecError(
                f"PR {pr_id} not mergeable: problems={pr.problems}, "
                f"approvers={pr.approvers} (need {min_approvers})")
        self.merged[pr.spec["name"]] = dict(pr.spec)
        pr.status = "merged"
        return pr.spec["name"]

    def load(self, name: str) -> Dict[str, Any]:
        if name not in self.merged:
            raise KeyError(f"template {name!r} not merged")
        return dict(self.merged[name])

    def names(self) -> List[str]:
        return sorted(self.merged.keys())


def render_pr(spec: Dict[str, Any], author: str,
              repo: str = "JarvisCao168/charter-orchestrator") -> Dict[str, str]:
    """Render a GitHub PR body + filename for a community template submission.

    A real marketplace POSTs this to the repo; here we just produce the
    exact payload so a human (or CI) can open the PR.
    """
    fname = f"charter/templates/{spec['name']}.json"
    title = (f"Add SOP template: {spec['label']} ({spec['name']})"
             if spec.get("label") and spec.get("label") != spec["name"]
             else f"Add SOP template: {spec['name']}")
    body = "\n".join([
        f"# Community SOP Template: {spec.get('label', spec['name'])}",
        "",
        f"Submitted by: {author}",
        "",
        "## Template JSON",
        "```json",
        json.dumps(spec, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Review checklist",
        "- [ ] schema valid (`validate_template` returns [])",
        "- [ ] gate checks reference real stage ids",
        "- [ ] guardrail regexes compile",
        "- [ ] TDD level + token budget sane for the domain",
        "- [ ] a teammate approved",
        "",
        "Merge command: `python -m charter.cli template-merge <name>` "
        "(or the marketplace's `merge()`).",
    ])
    return {"repo": repo, "filename": fname, "title": title,
            "body": body, "json": json.dumps(spec, indent=2, ensure_ascii=False)}
