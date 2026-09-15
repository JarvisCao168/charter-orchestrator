"""Real AWS IAM / S3 policy apply + audit for team checkpoints (v2.9).

Lifts `charter/checkpoint_iam.py` (policy *documents* as JSON) to
**applying** them to a real AWS account and auditing every apply:

    - `IamApplier` - when a `boto3` session + account are bound:
        * `apply(team_roles, team, ...)` - create the per-role IAM roles +
          attach the policies + put the S3 bucket policy, all via the
          IAM / S3 APIs.
        * `drift_report(...)` - read the live state and report which
          policies are missing / stale.
    - `IamAuditLog` - an append-only JSONL audit trail of every IAM / S3
      mutation (who, when, what, the ARN, success/fail).
    - `apply_iam_policies(...)` / `iam_drift_report(...)` /
      `iam_audit_report(...)` - the one-shot convenience wrappers.

Offline-safe: without a boto3 session / account, every method returns a
`dry-run` report carrying the *exact* API calls + args it WOULD make (so a
reviewer can apply them out-of-band), and nothing touches AWS. The audit
log records both live and dry-run operations.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .checkpoint_iam import iam_policy, s3_bucket_policy, render_iam_bundle

__all__ = [
    "IamApplier", "IamAuditLog",
    "apply_iam_policies", "iam_drift_report", "iam_audit_report",
]


class IamAuditLog:
    """Append-only JSONL audit trail of IAM / S3 mutations."""

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def record(self, op: str, actor: str, target: str,
               account: str, ok: bool, detail: str = "") -> None:
        entry = {
            "op": op, "ts": time.time(), "actor": actor,
            "target": target, "account": account, "ok": ok,
            "detail": detail,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def entries(self, limit: int = 500) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if not os.path.isfile(self.path):
            return out
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f.readlines()[-limit:]:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return out

    def report(self) -> Dict[str, Any]:
        entries = self.entries()
        by_op: Dict[str, int] = {}
        by_actor: Dict[str, int] = {}
        by_target: Dict[str, int] = {}
        failures = [e for e in entries if not e.get("ok", True)]
        for e in entries:
            by_op[e.get("op", "?")] = by_op.get(e.get("op", "?"), 0) + 1
            by_actor[e.get("actor", "?")] = \
                by_actor.get(e.get("actor", "?"), 0) + 1
            by_target[e.get("target", "?")] = \
                by_target.get(e.get("target", "?"), 0) + 1
        return {
            "total": len(entries),
            "failures": len(failures),
            "by_op": by_op, "by_actor": by_actor, "by_target": by_target,
            "last": entries[-1] if entries else None,
            "last_failure": failures[-1] if failures else None,
        }


@dataclass
class IamApplier:
    """Apply team checkpoint IAM / S3 policies to a real AWS account.

    `session` is a `boto3` session (or None for dry-run). `account_id`
    + `region` are used to build concrete ARNs. The applier is idempotent:
    it creates / updates roles + policies and puts the bucket policy.
    """
    session: Any = None
    account_id: str = "000000000000"
    region: str = "us-east-1"
    audit_log: Optional[IamAuditLog] = None
    team: str = "charter-team"
    bucket: str = "charter-checkpoints"
    actor: str = "charter"

    @property
    def live(self) -> bool:
        return self.session is not None

    def _iam(self):
        return self.session.client("iam")

    def _s3(self):
        return self.session.client("s3", region_name=self.region)

    def _log(self, op: str, target: str, ok: bool,
             detail: str = "") -> None:
        if self.audit_log:
            self.audit_log.record(op, self.actor, target,
                                   self.account_id, ok, detail)

    def apply(self, team_roles: Dict[str, List[str]],
              actor: Optional[str] = None) -> Dict[str, Any]:
        """Create the per-role IAM roles + attach policies + put the S3
        bucket policy. Dry-run (no session) returns the planned API calls
        without making them."""
        self.actor = actor or self.actor
        policies = iam_policy(team_roles, team=self.team,
                               bucket=self.bucket, region=self.region,
                               account_id=self.account_id)
        bpol = s3_bucket_policy(team_roles, team=self.team,
                                 bucket=self.bucket, region=self.region,
                                 account_id=self.account_id)
        if not self.live:
            return self._dry_run(policies, bpol)
        return self._live_apply(policies, bpol)

    def _dry_run(self, policies: Dict[str, Dict[str, Any]],
                 bpol: Dict[str, Any]) -> Dict[str, Any]:
        calls: List[Dict[str, Any]] = []
        role_arns: Dict[str, str] = {}
        for role, pol in policies.items():
            role_name = f"charter-{self.team}-{role}"
            role_arns[role] = (
                f"arn:aws:iam::{self.account_id}:role/{role_name}")
            # 1. create the role (a trust policy allowing the team's ECS /
            #    EC2 / Lambda to assume it)
            calls.append({
                "api": "iam.create_role",
                "RoleName": role_name,
                "AssumeRolePolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                        "Action": "sts:AssumeRole"},
                    ],
                },
                "Path": "/",
                "Tags": [{"Key": "charter-team", "Value": self.team}],
            })
            # 2. attach the inline policy (upsert; same API the live path uses)
            calls.append({
                "api": "iam.put_role_policy",
                "RoleName": role_name,
                "PolicyName": f"charter-{self.team}-{role}-checkpoint",
                "PolicyDocument": pol,
            })
        calls.append({
            "api": "s3.put_bucket_policy",
            "Bucket": self.bucket,
            "Policy": json.dumps(bpol, ensure_ascii=False),
        })
        for c in calls:
            self._log("iam.dry-run", c["api"], False,
                      "dry-run: would call " + c["api"])
        return {"applied": False, "dry_run": True,
                "role_arns": role_arns, "planned_calls": calls,
                "bucket_policy": bpol,
                "note": "no boto3 session; apply these calls out-of-band"}

    def _live_apply(self, policies: Dict[str, Dict[str, Any]],
                    bpol: Dict[str, Any]) -> Dict[str, Any]:
        iam = self._iam()
        s3 = self._s3()
        role_arns: Dict[str, str] = {}
        errors: List[str] = []
        for role, pol in policies.items():
            role_name = f"charter-{self.team}-{role}"
            # create role (idempotent: catch EntityAlreadyExists)
            try:
                resp = iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps({
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": {"Service":
                                           "ecs-tasks.amazonaws.com"},
                            "Action": "sts:AssumeRole"}],
                    }),
                    Tags=[{"Key": "charter-team", "Value": self.team}])
                role_arns[role] = resp["Role"]["Arn"]
                self._log("iam.create_role", role_name, True,
                           role_arns[role])
            except Exception:
                # role exists; fetch its ARN
                arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
                role_arns[role] = arn
                self._log("iam.get_role", role_name, True, arn)
            # attach the inline policy (upsert)
            try:
                iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName=f"charter-{self.team}-{role}-checkpoint",
                    PolicyDocument=json.dumps(pol, ensure_ascii=False))
                self._log("iam.put_role_policy", role_name, True,
                           "policy attached")
            except Exception as exc:
                errors.append(f"{role}: {str(exc)[:120]}")
                self._log("iam.apply", role_name, False, str(exc)[:200])
        # put the bucket policy
        try:
            s3.put_bucket_policy(
                Bucket=self.bucket,
                Policy=json.dumps(bpol, ensure_ascii=False))
            self._log("s3.put_bucket_policy", self.bucket, True,
                       "bucket policy applied")
        except Exception as exc:
            errors.append(f"bucket-policy: {str(exc)[:120]}")
            self._log("s3.put_bucket_policy", self.bucket, False,
                       str(exc)[:200])
        return {"applied": not errors, "dry_run": False,
                "role_arns": role_arns, "errors": errors}

    def drift_report(self,
                     team_roles: Dict[str, List[str]]) -> Dict[str, Any]:
        """Read the live state and report which roles / policies are
        missing or stale. Dry-run (no session) returns an empty drift
        report with `live=False`."""
        policies = iam_policy(team_roles, team=self.team,
                               bucket=self.bucket, region=self.region,
                               account_id=self.account_id)
        if not self.live:
            return {"live": False, "drift": [],
                    "expected_roles": list(policies.keys()),
                    "note": "no boto3 session; cannot read live state"}
        iam = self._iam()
        drift: List[Dict[str, Any]] = []
        for role, pol in policies.items():
            role_name = f"charter-{self.team}-{role}"
            try:
                iam.get_role(RoleName=role_name)
            except Exception:
                drift.append({"kind": "missing-role", "role": role_name})
                continue
            try:
                p = iam.get_role_policy(
                    RoleName=role_name,
                    PolicyName=f"charter-{self.team}-{role}-checkpoint")
                if p.get("PolicyDocument") != pol:
                    drift.append({"kind": "stale-policy", "role": role_name})
            except Exception:
                drift.append({"kind": "missing-policy", "role": role_name})
        return {"live": True, "drift": drift,
                "expected_roles": list(policies.keys())}


# ---------------------------------------------------------------------------
# Module-level convenience (audit log at the default path)
# ---------------------------------------------------------------------------
_audit_cache: Dict[str, IamAuditLog] = {}


def _get_audit(audit_path: Optional[str] = None) -> IamAuditLog:
    path = audit_path or os.path.join(
        os.path.expanduser("~"), ".charter", "iam_audit.log")
    key = path
    if key not in _audit_cache:
        _audit_cache[key] = IamAuditLog(path)
    return _audit_cache[key]


def apply_iam_policies(
        team_roles: Dict[str, List[str]],
        team: str = "charter-team",
        account_id: str = "000000000000",
        region: str = "us-east-1",
        session: Any = None,
        actor: str = "charter",
        audit_path: Optional[str] = None) -> Dict[str, Any]:
    """tool: apply_iam_policies - apply the team's checkpoint IAM / S3
    policies to a real AWS account (dry-run when no session)."""
    applier = IamApplier(
        session=session, account_id=account_id, region=region,
        team=team, audit_log=_get_audit(audit_path), actor=actor)
    return applier.apply(team_roles, actor=actor)


def iam_drift_report(
        team_roles: Dict[str, List[str]],
        team: str = "charter-team",
        account_id: str = "000000000000",
        region: str = "us-east-1",
        session: Any = None) -> Dict[str, Any]:
    """tool: iam_drift_report - check the live IAM / S3 state against the
    expected team policies."""
    applier = IamApplier(
        session=session, account_id=account_id, region=region, team=team)
    return applier.drift_report(team_roles)


def iam_audit_report(
        audit_path: Optional[str] = None) -> Dict[str, Any]:
    """tool: iam_audit_report - the IAM / S3 mutation audit trail."""
    return _get_audit(audit_path).report()
