"""Team RBAC + S3 versioning / cross-region replication for shared
checkpoints (v2.7).

Lifts `charter/checkpoint_shared.py` (single-bucket shared store + audit
log) to a **team-grade** setup:

    - `TeamRBAC` - a coarse role model (owner / admin / member / viewer)
      over a team, with per-operation allow/deny for
      {publish, pull, import, audit}. `check(role, op)` is the one-call
      gate; `enforce(actor_role, op, store)` wraps a
      `SharedCheckpointStore` call so the team policy is applied before
      the op hits the backend.
    - `s3_versioning_config(bucket)` - the S3 bucket-versioning JSON
      (Enabled + MFADecodeAllowed) so deleted / overwritten checkpoints
      are retained.
    - `s3_cross_region_replication(bucket, source_region,
      destination_bucket, destination_region, team_label)` - an S3 CRR
      replication rule that mirrors checkpoints to a second region (with
      a team label filter), plus the destination bucket's versioning.
    - `team_policies(team_roles, bucket, source_region,
      destination_bucket, destination_region)` - one-shot: the RBAC
      table + versioning + CRR docs, all JSON-ready.

Stdlib-only. No AWS dep: the configs are pure JSON (the S3 console /
CLI / IaC accepts them). The live RBAC gate (`TeamRBAC.enforce`) works
fully offline.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "TeamRBAC", "TeamPolicy",
    "s3_versioning_config", "s3_cross_region_replication",
    "team_policies",
]

# role -> allowed ops
_ROLE_OPS: Dict[str, set] = {
    "owner": {"publish", "pull", "import", "audit", "rbac"},
    "admin": {"publish", "pull", "import", "audit"},
    "member": {"publish", "pull", "import"},
    "viewer": {"pull"},
}
_ALL_OPS = ("publish", "pull", "import", "audit", "rbac")


@dataclass
class TeamPolicy:
    """One team's RBAC table + the S3 backend config it governs."""
    team: str
    roles: Dict[str, List[str]]          # {role: [usernames]}
    s3_bucket: str = "charter-checkpoints"
    source_region: str = "us-east-1"
    versioning_enabled: bool = True
    cross_region_replication: bool = False
    destination_bucket: str = ""
    destination_region: str = ""
    team_label: str = "charter"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "team": self.team,
            "roles": self.roles,
            "s3_bucket": self.s3_bucket,
            "source_region": self.source_region,
            "versioning_enabled": self.versioning_enabled,
            "cross_region_replication": self.cross_region_replication,
            "destination_bucket": self.destination_bucket,
            "destination_region": self.destination_region,
            "team_label": self.team_label,
        }


class TeamRBAC:
    """A coarse team RBAC gate for checkpoint ops.

    Roles: owner > admin > member > viewer. `check(role, op)` returns
    True when that role is allowed `op` (the role hierarchy is
    precomputed in `_ROLE_OPS`). `enforce(actor_role, op, fn, *a, **k)`
    runs `fn` only when the role is allowed; otherwise it returns a
    `{"ok": False, "reason": "rbac-deny: ..."}` report *without*
    calling `fn`.
    """

    def __init__(self, roles: Optional[Dict[str, List[str]]] = None) -> None:
        # roles maps role -> [usernames]; we mainly care about the role
        # names present. If roles is None, all 4 roles are defined but
        # unassigned (the gate still works on role names).
        self.roles = roles or {}

    def check(self, role: str, op: str) -> bool:
        """Is `role` allowed to perform `op`? (owner gets all; a role
        that isn't in `_ROLE_OPS` is denied by default.)"""
        role = (role or "").lower()
        op = (op or "").lower()
        if op not in _ALL_OPS:
            return False
        allowed = _ROLE_OPS.get(role, set())
        return op in allowed

    def user_role(self, username: str) -> Optional[str]:
        """Which role(s) a username belongs to (first match, owner
        preferred). Returns None if the user isn't in any role."""
        username = (username or "").lower()
        for role in ("owner", "admin", "member", "viewer"):
            if username in [u.lower() for u in
                            self.roles.get(role, [])]:
                return role
        return None

    def allow_user(self, username: str, op: str) -> bool:
        role = self.user_role(username)
        if role is None:
            return False
        return self.check(role, op)

    def enforce(self, actor_role: str, op: str, fn, *args,
                **kwargs) -> Dict[str, Any]:
        """Gate an operation on the RBAC policy.

        `fn` is the actual op (e.g. a store method). If the role is
        allowed, `fn` runs and `{"ok": True, "result": ...}` is
        returned. Otherwise `fn` is NOT called and `{"ok": False,
        "reason": "rbac-deny:<op>"}` is returned.
        """
        if self.check(actor_role, op):
            return {"ok": True, "result": fn(*args, **kwargs),
                    "role": actor_role, "op": op}
        return {"ok": False,
                "reason": f"rbac-deny:{op} (role={actor_role})",
                "role": actor_role, "op": op}


def s3_versioning_config(bucket: str,
                         mfadecode: bool = True) -> Dict[str, Any]:
    """S3 bucket-versioning config (Enabled + MFADecodeAllowed) so
    checkpoint objects are retained on delete / overwrite."""
    return {
        "VersioningConfiguration": {
            "Status": "Enabled",
            "MFADecodeAllowed": mfadecode,
            "MFA": {"SerialNumber": "arn:aws:iam::000000000000:mfa/charter",
                     "Token": "00000"},
        },
        "bucket": bucket,
    }


def s3_cross_region_replication(
        bucket: str,
        source_region: str,
        destination_bucket: str,
        destination_region: str,
        team_label: str = "charter",
        versioning_enabled: bool = True,
        ) -> Dict[str, Any]:
    """S3 CRR replication rule mirroring a team's checkpoints to a second
    region (with a team-label filter), plus the destination bucket's
    versioning. The source bucket must also have versioning enabled."""
    arn_repl = (f"arn:aws:s3:::{destination_bucket}")
    rule: Dict[str, Any] = {
        "ID": f"charter-{team_label}-{team_label}",
        "Status": "Enabled",
        "Prefix": f"{team_label}/",
        "Filter": {"Prefix": [f"{team_label}/"]},
        "Destination": {
            "Bucket": arn_repl,
            "StorageClass": "STANDARD",
            "ReplicationTime": {"TimeAfterSeconds": 60},
            "DeleteMarkerReplication": {"Status": "Enabled"},
        },
        "SourceSelectionCriteria": {
            "ReplicaModifications": {"Status": "Enabled"},
        },
    }
    return {
        "ReplicationConfiguration": {"Role": (
            "arn:aws:iam::000000000000:role/charter-repl-" + team_label),
                                       "Rules": [rule]},
        "source_bucket": bucket,
        "source_region": source_region,
        "destination_bucket": destination_bucket,
        "destination_region": destination_region,
        "destination_versioning": s3_versioning_config(
            destination_bucket, mfadecode=versioning_enabled),
    }


def team_policies(team_roles: Dict[str, List[str]],
                  team: str = "charter-team",
                  bucket: str = "charter-checkpoints",
                  source_region: str = "us-east-1",
                  destination_bucket: Optional[str] = None,
                  destination_region: Optional[str] = None,
                  team_label: str = "charter",
                  enable_crr: bool = False) -> Dict[str, str]:
    """tool: team_policies - one-shot team checkpoint policy bundle.

    Returns:
        rbac       JSON of {team, roles, role_op_matrix}
        versioning JSON of the source bucket's versioning config
        crr        JSON of the cross-region replication config (only when
                   `enable_crr` is True; else "{}")
        summary    a short human-readable digest
    """
    # RBAC table
    rbac_table: Dict[str, Any] = {
        "team": team,
        "roles": team_roles,
        "role_op_matrix": {
            role: sorted(ops)
            for role, ops in _ROLE_OPS.items()
        },
        "all_ops": list(_ALL_OPS),
        "ts": time.time(),
    }
    versioning = s3_versioning_config(bucket)
    if enable_crr and destination_bucket and destination_region:
        crr = s3_cross_region_replication(
            bucket, source_region, destination_bucket,
            destination_region, team_label=team_label)
    else:
        crr = {}
    summary = (
        f"team={team} | roles={list(team_roles.keys())} | "
        f"bucket={bucket}@{source_region} | versioning=on | "
        f"crr={'on->' + destination_bucket + '@' + destination_region
                 if (enable_crr and destination_bucket) else 'off'}")
    return {
        "rbac": json.dumps(rbac_table, indent=2, ensure_ascii=False),
        "versioning": json.dumps(versioning, indent=2),
        "crr": json.dumps(crr, indent=2, ensure_ascii=False),
        "summary": summary,
    }
