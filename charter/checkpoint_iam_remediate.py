"""Checkpoint IAM real AWS apply + automatic drift remediation (v2.10).

Lifts `charter/checkpoint_iam_apply.py` (apply the team policies to a
boto3 session + audit) to a **self-healing** controller: after applying,
it reads the live IAM / S3 state, detects drift (a role missing, a
policy stale, a bucket policy absent), and *remediates* it — re-applying
only what drifted — in a single reconcile pass. This mirrors a
K8s-controller `observe -> reconcile -> act` loop, but for IAM / S3.

    - `IamRemediator` - the controller:
        * `reconcile(team_roles, ...)` - observe the live state
          (drift_report), then remediate each drift (create the missing
          role, upsert the stale policy, put the bucket policy) and
          re-check; returns a reconcile report.
        * `auto_remediate(dry_run)` - a one-pass remediation + verify,
          with a JSONL audit trail of every mutation.
    - `IamDriftRemediation` - one concrete drift + the action taken to
      fix it.
    - `reconcile_iam(team_roles, ...)` - the one-shot entry point.

`boto3` is the live backend (a real account when a session is bound);
without a session every operation is a **dry-run** that records exactly
what WOULD change, and the audit log is still written - so the
reconciliation loop is fully testable offline (mock the session, as
v2.9's mock-boto3 did) and runs in CI.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .checkpoint_iam_apply import (
    IamApplier,
    IamAuditLog,
    _get_audit,
)
from .checkpoint_iam import iam_policy, s3_bucket_policy

__all__ = [
    "IamRemediator", "IamDriftRemediation", "reconcile_iam",
]


@dataclass
class IamDriftRemediation:
    """One detected drift + the action that fixed it."""
    drift_kind: str          # "missing-role" | "stale-policy" | "missing-bucket-policy"
    target: str
    remediated: bool
    action: str = ""
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return {"drift_kind": self.drift_kind, "target": self.target,
                "remediated": self.remediated, "action": self.action,
                "ts": self.ts}


@dataclass
class IamRemediator:
    """A self-healing IAM / S3 checkpoint controller.

    `session` is a boto3 session (live) or None (dry-run). Each
    `reconcile` observes the live drift, remediates it, and re-checks;
    the audit log records every mutation.
    """
    session: Any = None
    account_id: str = "000000000000"
    region: str = "us-east-1"
    team: str = "charter-team"
    bucket: str = ""            # empty -> derive "charter-{team}-checkpoints"
    audit_log: Optional[IamAuditLog] = None
    actor: str = "charter-remediator"
    applier: Optional[IamApplier] = None

    def __post_init__(self) -> None:
        # derive the team-prefixed bucket when not explicitly set (matches
        # IamApplier's default of "charter-{team}-checkpoints")
        bucket = self.bucket or f"charter-{self.team}-checkpoints"
        self.bucket = bucket
        self.applier = IamApplier(
            session=self.session, account_id=self.account_id,
            region=self.region, team=self.team, bucket=self.bucket,
            audit_log=self.audit_log, actor=self.actor)

    def _log(self, op: str, target: str, ok: bool,
             detail: str = "") -> None:
        if self.audit_log:
            self.audit_log.record(op, self.actor, target,
                                   self.account_id, ok, detail)

    # -- observe ---------------------------------------------------------
    def observe(self, team_roles: Dict[str, List[str]]
                ) -> List[Dict[str, Any]]:
        """Read the live drift (delegates to `IamApplier.drift_report`)."""
        dr = self.applier.drift_report(team_roles)
        # expand the drift_report's `drift` list (missing-role /
        # missing-policy / stale-policy) + a bucket-policy check.
        out = list(dr.get("drift", []))
        if not dr.get("live", False):
            # dry-run: we can't observe live state; report "expected"
            # entries as the plan.
            return [{
                "drift_kind": "dry-run-expect",
                "target": f"role:charter-{self.team}-{r}",
            } for r in team_roles] + [
                {"drift_kind": "dry-run-expect",
                 "target": f"bucket:{self.bucket}"}]
        return out

    # -- act -----------------------------------------------------------
    def _remediate_one(self, drift: Dict[str, Any],
                       team_roles: Dict[str, List[str]]
                       ) -> IamDriftRemediation:
        kind = drift.get("drift_kind", "unknown")
        target = drift.get("target", "")
        action = ""
        ok = False
        if not self.applier.live:
            # dry-run: record the intended action, don't call AWS
            action = (f"dry-run: would {kind} -> {target}")
            ok = True
        else:
            iam = self.applier._iam()
            s3 = self.applier._s3()
            try:
                if kind == "missing-role":
                    role_name = target.split(":")[-1]
                    iam.create_role(
                        RoleName=role_name,
                        AssumeRolePolicyDocument=json.dumps({
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Principal": {"Service":
                                               "ecs-tasks.amazonaws.com"},
                                "Action": "sts:AssumeRole"}],
                        }),
                        Tags=[{"Key": "charter-team",
                                "Value": self.team}])
                    action = f"created role {role_name}"
                    ok = True
                elif kind in ("stale-policy", "missing-policy"):
                    role_name = target.split(":")[-1]
                    role = _role_from_name(role_name, self.team)
                    pol = iam_policy({role: ["x"]}, team=self.team,
                                     bucket=self.bucket, region=self.region,
                                     account_id=self.account_id)
                    iam.put_role_policy(
                        RoleName=role_name,
                        PolicyName=f"charter-{self.team}-{role}-checkpoint",
                        PolicyDocument=json.dumps(
                            pol.get(role, {}), ensure_ascii=False))
                    action = f"re-applied policy on {role_name}"
                    ok = True
                elif kind == "missing-bucket-policy":
                    bpol = s3_bucket_policy(
                        team_roles, team=self.team, bucket=self.bucket,
                        region=self.region, account_id=self.account_id)
                    s3.put_bucket_policy(
                        Bucket=self.bucket,
                        Policy=json.dumps(bpol, ensure_ascii=False))
                    action = f"put bucket policy on {self.bucket}"
                    ok = True
                else:
                    action = f"no remediation for drift kind {kind!r}"
                    ok = False
            except Exception as exc:
                action = f"failed to remediate {kind}: {str(exc)[:160]}"
                ok = False
        self._log(f"iam.remediate.{kind}", target, ok, action)
        return IamDriftRemediation(
            drift_kind=kind, target=target, remediated=ok,
            action=action)

    def _role_from_name(self, role_name: str) -> str:
        base = f"charter-{self.team}-"
        return role_name[len(base):] if role_name.startswith(base) \
            else "member"

    # -- reconcile (the controller loop) ---------------------------------
    def reconcile(self, team_roles: Dict[str, List[str]],
                  max_passes: int = 2) -> Dict[str, Any]:
        """observe -> remediate -> re-observe, up to `max_passes` times.
        Stops when no drift remains. Returns a reconcile report with the
        per-pass drift + the remediations taken."""
        passes: List[Dict[str, Any]] = []
        for p in range(max_passes):
            drifts = self.observe(team_roles)
            remediations: List[IamDriftRemediation] = []
            for d in drifts:
                # only remediate the actionable kinds
                if d.get("drift_kind") in ("missing-role", "stale-policy",
                                           "missing-policy",
                                           "missing-bucket-policy",
                                           "dry-run-expect"):
                    remediations.append(self._remediate_one(d, team_roles))
            this_pass = {
                "pass": p + 1,
                "drifts": drifts,
                "remediations": [r.as_dict() for r in remediations],
                "all_remediated": all(r.remediated for r in remediations)
                if remediations else True,
                "clean": not drifts,
            }
            passes.append(this_pass)
            if this_pass["clean"] or not any(
                    d.get("drift_kind") in ("missing-role", "stale-policy",
                                             "missing-policy",
                                             "missing-bucket-policy")
                    for d in drifts):
                break
        converged = passes[-1]["clean"] if passes else False
        return {
            "converged": converged,
            "passes": passes,
            "live": self.applier.live,
            "summary": (
                f"{'converged' if converged else 'not-converged'} "
                f"after {len(passes)} pass(es) "
                f"({'dry-run' if not self.applier.live else 'live'})"),
        }

    def auto_remediate(self, team_roles: Dict[str, List[str]],
                       dry_run: bool = False) -> Dict[str, Any]:
        """A one-pass remediation + verify (the `reconcile` with
        `max_passes=2`). `dry_run` forces a no-AWS observe/act pass."""
        if dry_run:
            applier_live = self.applier.live
            # force a dry-run observe/act by temporarily clearing the
            # session (the applier falls back to dry-run paths)
            self.applier.session = None
            try:
                out = self.reconcile(team_roles, max_passes=1)
            finally:
                self.applier.session = applier_live
            out["forced_dry_run"] = True
            return out
        return self.reconcile(team_roles, max_passes=2)


def _role_from_name(role_name: str, team: str) -> str:
    base = f"charter-{team}-"
    return role_name[len(base):] if role_name.startswith(base) \
        else "member"


def reconcile_iam(
        team_roles: Dict[str, List[str]],
        team: str = "charter-team",
        account_id: str = "000000000000",
        region: str = "us-east-1",
        session: Any = None,
        actor: str = "charter-remediator",
        audit_path: Optional[str] = None,
        dry_run: bool = False,
        ) -> Dict[str, Any]:
    """tool: reconcile_iam - observe + auto-remediate the team's IAM / S3
    checkpoint state.

    Live when `session` is a boto3 session; dry-run otherwise (the
    intended actions are recorded, nothing touches AWS). Returns the
    `IamRemediator.auto_remediate` / `reconcile` report + an audit-tail
    digest.
    """
    remediator = IamRemediator(
        session=session, account_id=account_id, region=region,
        team=team, audit_log=_get_audit(audit_path), actor=actor)
    out = remediator.auto_remediate(team_roles, dry_run=dry_run)
    out["audit"] = remediator.audit_log.report() \
        if remediator.audit_log else {}
    return out
