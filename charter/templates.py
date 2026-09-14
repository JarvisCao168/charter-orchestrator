"""Industry SOP template marketplace (v2.0).

Lets teams start from a pre-governed 10-stage SOP tuned to their domain
instead of the generic default. Templates are JSON documents loaded from
`charter/templates/*.json`; each overrides stage gate checks, TDD level,
token budget, and guardrail patterns.

Builtin ship in this module; a "marketplace" = drop a new JSON into
`charter/templates/` (or the user's `~/.charter/templates/`) and call
`load_template(name)`.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Builtin templates (also persisted as JSON for discovery / marketplace)
# ---------------------------------------------------------------------------
BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "finance": {
        "name": "finance",
        "label": "Finance & Regulated (SOC2-aligned)",
        "stage_gates": {
            "stage_4": ["architecture_doc_locked", "tech_selection",
                         "security_review_signed"],
            "stage_5": ["env_ready", "ci_green", "human_approver",
                         "compliance_signoff"],
            "stage_7": ["integration_tests_passed", "acceptance_signed",
                         "audit_log_exported"],
            "stage_8": ["release_checklist", "artifacts_built",
                         "rollback_plan_signed"],
        },
        "tdd_enforcement": "strict",
        "token_budget": 60_000,
        "guardrail_extra_patterns": [
            r"(?i)select\s+.*password",
            r"(?i)exfiltrat",
        ],
        "audit_required_stages": ["stage_5", "stage_7", "stage_8"],
    },
    "healthcare": {
        "name": "healthcare",
        "label": "Healthcare & HIPAA",
        "stage_gates": {
            "stage_4": ["architecture_doc_locked", "tech_selection",
                         "data_class_plan"],
            "stage_5": ["env_ready", "ci_green", "human_approver",
                         "phi_handling_review"],
            "stage_7": ["integration_tests_passed", "acceptance_signed",
                         "phi_encryption_verified"],
        },
        "tdd_enforcement": "strict",
        "token_budget": 50_000,
        "guardrail_extra_patterns": [
            r"(?i)\b(hipaa|phi|patient)\s+data",
            r"ssn\s*[:=]",
        ],
        "audit_required_stages": ["stage_4", "stage_5", "stage_7"],
    },
    "e-commerce": {
        "name": "e-commerce",
        "label": "E-commerce / High-throughput",
        "stage_gates": {
            "stage_6": ["tdd_red_green", "worktree_isolated",
                         "code_review_passed", "load_test_passed"],
            "stage_8": ["release_checklist", "artifacts_built",
                         "canary_deployment_verified"],
        },
        "tdd_enforcement": "soft",
        "token_budget": 150_000,
        "guardrail_extra_patterns": [
            r"(?i)price\s*=\s*0\b",
            r"(?i)coupon\s*unlimited",
        ],
        "audit_required_stages": ["stage_8"],
    },
    "research": {
        "name": "research",
        "label": "Research / Experimentation",
        "stage_gates": {
            "stage_1": ["problem_statement", "feasibility_score",
                         "hypothesis_stated"],
            "stage_7": ["integration_tests_passed", "reproducibility_checked"],
        },
        "tdd_enforcement": "off",
        "token_budget": 300_000,
        "guardrail_extra_patterns": [],
        "audit_required_stages": [],
    },
}


def _template_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "templates")


def list_templates() -> List[Dict[str, str]]:
    """All available templates: builtin + any dropped-in JSON files."""
    out = [{"name": k, "label": v["label"]} for k, v in BUILTIN_TEMPLATES.items()]
    tdir = _template_dir()
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if fn.endswith(".json"):
                name = fn[:-5]
                if name not in BUILTIN_TEMPLATES and not any(o["name"] == name for o in out):
                    out.append({"name": name, "label": f"{name} (custom)"})
    return out


def load_template(name: str) -> Dict[str, Any]:
    """Load a template by name (builtin or dropped-in JSON)."""
    if name in BUILTIN_TEMPLATES:
        return dict(BUILTIN_TEMPLATES[name])
    tdir = _template_dir()
    path = os.path.join(tdir, f"{name}.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("name", name)
        return data
    raise KeyError(f"unknown template {name!r}; available: {[o['name'] for o in list_templates()]}")


def apply_template(project_config: Dict[str, Any],
                   name: str) -> Dict[str, Any]:
    """Merge a template's overrides into a project config (in place + return)."""
    tpl = load_template(name)
    project_config.setdefault("stage_gates", {}).update(tpl.get("stage_gates", {}))
    if "tdd_enforcement" in tpl:
        project_config["tdd_enforcement"] = tpl["tdd_enforcement"]
    if "token_budget" in tpl:
        project_config["token_budget"] = tpl["token_budget"]
    if "guardrail_extra_patterns" in tpl:
        project_config.setdefault("guardrail_extra_patterns", [])
        for p in tpl["guardrail_extra_patterns"]:
            if p not in project_config["guardrail_extra_patterns"]:
                project_config["guardrail_extra_patterns"].append(p)
    if "audit_required_stages" in tpl:
        project_config["audit_required_stages"] = tpl["audit_required_stages"]
    project_config["template"] = name
    return project_config
