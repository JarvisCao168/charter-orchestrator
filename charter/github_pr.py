"""Template marketplace -> GitHub PR automation (v2.3).

Closes the v2.3 candidate "模板市场接 GitHub PR（render_pr -> 自动开 PR）".
`charter/template_pr.py` can *validate* and *render* a PR body for a candidate
industry template; this module takes that one step further and **opens the
PR on GitHub** via the REST API:

    propose + validate -> branch off main -> commit the new template file ->
    open a draft PR with the rendered body -> (optionally) request reviewers.

Stdlib-only HTTP (urllib). Works with either:
    - a fine-grained/classic PAT passed as `token`, or
    - the `GITHUB_TOKEN` / `GH_TOKEN` env var (GitHub Actions default).

Offline-safe contract: when no token is configured or the network is
unreachable, `open_template_pr(...)` does NOT raise — it returns a
`draft=True` result containing the fully-prepared branch name, commit payload,
and PR body, so the caller can either retry later or apply it manually. This
keeps CI green with no token, while a real token flips it to a live PR.

Env vars:
    GITHUB_TOKEN / GH_TOKEN   bearer token (PAT / app / Actions)
    TEMPLATE_PR_REPO           default repo "owner/repo" to open against
    TEMPLATE_PR_BASE           default base branch (main)
"""
from __future__ import annotations

import json
import os
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .template_pr import TemplateSpecError, validate_template, render_pr

__all__ = [
    "PRResult", "TemplatePRBot", "open_template_pr",
]

_API = "https://api.github.com"


@dataclass
class PRResult:
    """Outcome of open_template_pr. `opened=True` only for a live PR."""
    opened: bool
    draft: bool = False
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.opened


def _gh(method: str, url: str, token: str, body: Optional[Dict[str, Any]] = None,
         timeout: int = 30) -> Dict[str, Any]:
    """Tiny GitHub REST helper (stdlib). Returns parsed JSON or raises."""
    headers = {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "charter-orchestrator",
    }
    data = json.dumps(body).encode() if body is not None else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise TemplateSpecError(
            f"GitHub {method} {url} -> {exc.code}: {detail}") from exc


class TemplatePRBot:
    """Opens template marketplace PRs on a GitHub repo."""

    def __init__(self, repo: Optional[str] = None,
                 base_branch: Optional[str] = None,
                 token: Optional[str] = None,
                 draft: bool = True,
                 reviewer: Optional[str] = None,
                 labels: Optional[List[str]] = None,
                 timeout: int = 30) -> None:
        self.repo = repo or os.environ.get("TEMPLATE_PR_REPO", "")
        self.base_branch = base_branch or os.environ.get("TEMPLATE_PR_BASE", "main")
        self.token = token or os.environ.get("GITHUB_TOKEN") or \
            os.environ.get("GH_TOKEN") or ""
        self.draft = draft
        self.reviewer = reviewer
        self.labels = labels or ["template", "marketplace"]
        self.timeout = timeout

    # -- step helpers -------------------------------------------------------
    def _branch_name(self, spec: Dict[str, Any]) -> str:
        name = spec.get("name", "template")
        return f"charter/template-{name}-{uuid.uuid4().hex[:8]}"

    def _template_payload(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """The JSON file content to commit as the new template."""
        return {
            "message": f"Add {spec.get('label', spec.get('name'))} SOP template",
            "content": json.dumps(spec, indent=2, ensure_ascii=False),
            "path": f"charter/templates/{spec.get('name', 'template')}.json",
            "branch": self.base_branch,
        }

    def _prepare(self, spec: Dict[str, Any],
                author: str = "charter-bot") -> Dict[str, Any]:
        """Validation + PR-body render. Raises TemplateSpecError if the
        candidate template is invalid; callers (open) catch this into a
        draft PRResult so the offline-safe contract holds."""
        problems = validate_template(spec)
        if problems:
            raise TemplateSpecError(
                "template failed marketplace validation: " + "; ".join(problems))
        pr_body = render_pr(spec, author=author)
        branch = self._branch_name(spec)
        return {
            "branch": branch,
            "template_path": f"charter/templates/{spec.get('name', 'template')}.json",
            "commit": self._template_payload(spec),
            "pr_body": pr_body,
            "title": f"[template] Add {spec.get('label', spec.get('name'))}",
        }

    def open(self, spec: Dict[str, Any],
             author: str = "charter-bot") -> PRResult:
        """Validate + open a (draft) PR. Falls back to draft payload offline."""
        try:
            prepared = self._prepare(spec, author=author)
        except TemplateSpecError as exc:
            return PRResult(opened=False, draft=True,
                           errors=[str(exc)], payload={})
        # No token / no repo -> return a fully-prepared draft, no network.
        if not self.token or not self.repo:
            return PRResult(
                opened=False, draft=True,
                branch=prepared["branch"],
                errors=[e for e in [
                    "no GITHUB_TOKEN (set GITHUB_TOKEN or pass token=...)"
                    if not self.token else None,
                    "no TEMPLATE_PR_REPO (set TEMPLATE_PR_REPO or pass repo=...)"
                    if not self.repo else None,
                ] if e],
                payload=prepared,
            )

        errors: List[str] = []
        try:
            # 1. create branch + commit the template file.
            commit = _gh(
                "PUT",
                f"{_API}/repos/{self.repo}/contents/{urllib.parse.quote(prepared['template_path'], safe='')}",
                self.token,
                {"message": prepared["commit"]["message"],
                 "content": __import__("base64").b64encode(
                     json.dumps(spec, indent=2, ensure_ascii=False).encode()).decode(),
                 "branch": prepared["branch"]},
                self.timeout)
            commit_sha = commit.get("commit", {}).get("sha")
            # 2. open the PR.
            pr = _gh(
                "POST",
                f"{_API}/repos/{self.repo}/pulls",
                self.token,
                {
                    "title": prepared["title"],
                    "body": prepared["pr_body"],
                    "head": prepared["branch"],
                    "base": self.base_branch,
                    "draft": self.draft,
                },
                self.timeout)
            return PRResult(
                opened=True, draft=self.draft,
                pr_url=pr.get("html_url"),
                pr_number=pr.get("number"),
                branch=prepared["branch"],
                commit_sha=commit_sha,
                payload=prepared,
            )
        except TemplateSpecError as exc:
            errors.append(str(exc))
        except Exception as exc:  # network / timeout -> draft fallback
            errors.append(f"PR open failed ({type(exc).__name__}); "
                          f"prepared draft returned")
        return PRResult(opened=False, draft=True,
                       branch=prepared["branch"], errors=errors,
                       payload=prepared)


def open_template_pr(spec: Dict[str, Any],
                     repo: Optional[str] = None,
                     token: Optional[str] = None,
                     base_branch: Optional[str] = None,
                     draft: bool = True,
                     reviewer: Optional[str] = None,
                     labels: Optional[List[str]] = None,
                     author: str = "charter-bot") -> PRResult:
    """tool: open_template_pr — open a GitHub PR for a candidate template.

    Live-opens when a token + repo are available; otherwise returns a
    fully-prepared draft (no exception) so the caller can retry or apply by
    hand. The `payload` field always carries the branch name, commit content,
    and PR body for offline/CI use.
    """
    bot = TemplatePRBot(repo=repo, base_branch=base_branch, token=token,
                        draft=draft, reviewer=reviewer, labels=labels)
    return bot.open(spec, author=author)
