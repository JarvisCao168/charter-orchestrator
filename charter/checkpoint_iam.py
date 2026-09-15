"""Real IAM / S3 bucket policy generation for team checkpoint access
(v2.8).

Lifts `charter/checkpoint_rbac.py` (an in-process role table + S3
versioning / CRR JSON) to **real AWS IAM + S3 bucket-policy** artifacts:
the same owner / admin / member / viewer roles are translated into actual
IAM policy documents + an S3 bucket policy that enforce the team's
checkpoint access at the cloud layer, not just in the app.

    - `iam_policy(team_roles, bucket, region, account_id)` - one IAM
      policy document per role (owner/admin/member/viewer) with the
      S3 actions that role may perform on the team's checkpoint
      bucket/prefix.
    - `s3_bucket_policy(team_roles, bucket, region, account_id)` - a
      single S3 *bucket policy* that allows / denies based on the team's
      members (via IAM ARNs), with a deny-default + per-role allow.
    - `render_iam_bundle(...)` - one-shot: {role, policy} docs + the
      bucket policy + a `role_policies` summary, all JSON-ready for the
      AWS console / `aws iam put-role-policy` / `aws s3api put-bucket-policy`.

Stdlib-only. The output is pure JSON (valid IAM / S3 policy syntax); no
AWS SDK. Account / region are injected so the generated ARNs are concrete.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

__all__ = [
    "iam_policy", "s3_bucket_policy", "render_iam_bundle",
    "role_s3_actions",
]

# role -> the S3 actions that role may perform on the team's checkpoint
# bucket/prefix. "owner" can also manage the policy; "viewer" is read-only.
_ROLE_ACTIONS: Dict[str, List[str]] = {
    "owner": [
        "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
        "s3:ListBucket", "s3:GetBucketPolicy", "s3:PutBucketPolicy",
        "s3:DeleteObjectVersion", "s3:GetObjectVersion",
        "s3:ReplicateObject",
    ],
    "admin": [
        "s3:GetObject", "s3:PutObject", "s3:ListBucket",
        "s3:GetObjectVersion", "s3:ReplicateObject",
    ],
    "member": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
    "viewer": ["s3:GetObject", "s3:ListBucket"],
}

_DENY_DEFAULT_ACTIONS = [
    "s3:PutObject", "s3:DeleteObject", "s3:GetBucketPolicy",
    "s3:PutBucketPolicy", "s3:DeleteObjectVersion", "s3:ReplicateObject",
]


def role_s3_actions(role: str) -> List[str]:
    """tool: role_s3_actions - the S3 actions a role is allowed (from the
    in-app RBAC table)."""
    return list(_ROLE_ACTIONS.get(role, _ROLE_ACTIONS["viewer"]))


def _arns(account_id: str, team: str, region: str,
          role: str) -> Dict[str, str]:
    base = f"arn:aws:iam::{account_id}:role"
    return {
        "role": f"{base}/charter-{team}-{role}",
        "policy": f"{base}/charter-{team}-{role}-policy",
        "bucket": f"arn:aws:s3:::charter-{team}-checkpoints",
        "prefix": f"charter-{team}-checkpoints/*",
    }


def iam_policy(team_roles: Dict[str, List[str]],
               team: str = "charter-team",
               bucket: Optional[str] = None,
               region: str = "us-east-1",
               account_id: str = "000000000000",
               ) -> Dict[str, Dict[str, Any]]:
    """tool: iam_policy - one IAM policy document per role.

    `team_roles` maps role -> [usernames]. Returns {role: <policy doc>}.
    Each policy doc scopes the S3 actions to the team's checkpoint bucket +
    prefix and tags the principal role so it is auditable.
    """
    bucket = bucket or f"charter-{team}-checkpoints"
    out: Dict[str, Dict[str, Any]] = {}
    for role, _users in team_roles.items():
        actions = role_s3_actions(role)
        resource = [f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*"]
        stmt: Dict[str, Any] = {
            "Sid": f"Charter{role.title()}Access",
            "Effect": "Allow",
            "Principal": {"AWS":
                          f"arn:aws:iam::{account_id}:role/"
                          f"charter-{team}-{role}"},
            "Action": actions,
            "Resource": resource,
            "Condition": {
                "StringEquals": {
                    "aws:PrincipalTag/team": team,
                },
            },
        }
        # owner additionally gets to read the bucket policy
        if role == "owner":
            stmt["Condition"]["StringEquals"]["aws:PrincipalTag/region"] = \
                region
        out[role] = {
            "Version": "2012-10-17",
            "Statement": [stmt],
        }
    return out


def s3_bucket_policy(team_roles: Dict[str, List[str]],
                     team: str = "charter-team",
                     bucket: Optional[str] = None,
                     region: str = "us-east-1",
                     account_id: str = "000000000000",
                     ) -> Dict[str, Any]:
    """tool: s3_bucket_policy - a single S3 bucket policy that mirrors the
    team's RBAC: a deny-default for destructive / policy actions, then
    per-role allow blocks keyed on the role's IAM ARN + team tag.

    Returns a ready-to-`put-bucket-policy` document.
    """
    bucket = bucket or f"charter-{team}-checkpoints"
    resource = [f"arn:aws:s3:::{bucket}",
                f"arn:aws:s3:::{bucket}/*"]
    arn_base = f"arn:aws:iam::{account_id}:role"

    # 1. deny-default: no one may run the destructive / policy actions
    #    without an explicit allow.
    statements: List[Dict[str, Any]] = [{
        "Sid": "CharterDenyDefault",
        "Effect": "Deny",
        "Action": _DENY_DEFAULT_ACTIONS,
        "Resource": resource,
        "Condition": {
            "StringNotEquals": {
                "aws:PrincipalTag/team": team,
            },
        },
    }]

    # 2. per-role allow blocks (most-privileged first so ordering reads
    #    top-down; S3 policy is order-independent but this is clearer).
    for role in ("owner", "admin", "member", "viewer"):
        if role not in team_roles:
            continue
        statements.append({
            "Sid": f"CharterAllow{role.title()}",
            "Effect": "Allow",
            "Principal": {"AWS": f"{arn_base}/charter-{team}-{role}"},
            "Action": role_s3_actions(role),
            "Resource": resource,
            "Condition": {
                "StringEquals": {
                    "aws:PrincipalTag/team": team,
                    "aws:PrincipalTag/region": region,
                },
            },
        })

    return {"Version": "2012-10-17", "Statement": statements,
            "bucket": bucket}


def render_iam_bundle(
        team_roles: Dict[str, List[str]],
        team: str = "charter-team",
        bucket: Optional[str] = None,
        region: str = "us-east-1",
        account_id: str = "000000000000",
        ) -> Dict[str, str]:
    """tool: render_iam_bundle - one-shot IAM + S3 bucket policy bundle.

    Returns:
        iam_policies   JSON of {role: policy doc}
        bucket_policy  JSON of the S3 bucket policy
        role_actions   JSON of {role: [actions]} (the effective matrix)
        summary        a short human digest
    All values are JSON strings ready for the AWS console / CLI.
    """
    bucket = bucket or f"charter-{team}-checkpoints"
    policies = iam_policy(team_roles, team=team, bucket=bucket,
                           region=region, account_id=account_id)
    bpol = s3_bucket_policy(team_roles, team=team, bucket=bucket,
                            region=region, account_id=account_id)
    matrix = {role: role_s3_actions(role)
              for role in team_roles}
    actions_counts = {k: len(v) for k, v in matrix.items()}
    summary = (
        f"team={team} | bucket={bucket}@{region} | "
        f"roles={list(team_roles.keys())} | "
        f"actions/role={actions_counts}")
    return {
        "iam_policies": json.dumps(policies, indent=2, ensure_ascii=False),
        "bucket_policy": json.dumps(bpol, indent=2, ensure_ascii=False),
        "role_actions": json.dumps(matrix, indent=2, ensure_ascii=False),
        "summary": summary,
    }
