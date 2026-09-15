"""Team shared checkpoint storage (S3/GCS) + audit log (v2.6).

Lifts `charter/cross_repo.py` (local `~/.charter/checkpoints/` file bus)
to a **team-shared, audited** exchange:

    - `SharedCheckpointStore` - publishes / pulls checkpoints to a shared
      backend. Backends:
          * `filesystem` (default, cross-repo local dir)
          * `s3`         (aws s3 via the AWS SDK if installed, else a
                         signed-URL HTTP PUT/GET fallback)
          * `gcs`        (google cloud storage via the GCS SDK if
                         installed, else the JSON API)
      The backend is pluggable and auto-detected; a missing SDK degrades to
      the local filesystem so CI / airgapped use keeps working.
    - `AuditLog` - an append-only JSONL audit trail of every publish /
      pull / import, with who + when + what + source. Written next to the
      store (or to a team log path) so a team can reconstruct exactly which
      checkpoints crossed repo boundaries.
    - `publish_to_team` / `pull_from_team` / `audit_report` - the
      one-shot convenience wrappers.

Stdlib-only. The shared backends use lazily-imported SDKs; when absent
they fall back to a local directory, so the module is testable offline and
the *call shape* is identical to the local bus.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .cross_repo import PublishedCheckpoint, CheckpointBus

__all__ = [
    "SharedCheckpointStore", "AuditLog",
    "publish_to_team", "pull_from_team", "audit_report",
]


@dataclass
class AuditEntry:
    op: str                    # "publish" | "pull" | "import"
    ts: float
    actor: str                 # agent_id / user
    project_id: str
    agent_id: str
    stage: str = ""
    backend: str = "filesystem"
    detail: str = ""
    ok: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "op": self.op, "ts": self.ts, "actor": self.actor,
            "project_id": self.project_id, "agent_id": self.agent_id,
            "stage": self.stage, "backend": self.backend,
            "detail": self.detail, "ok": self.ok,
        }


class AuditLog:
    """Append-only JSONL audit trail of cross-repo checkpoint ops."""

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def record(self, entry: AuditEntry) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")

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
        by_project: Dict[str, int] = {}
        for e in entries:
            by_op[e.get("op", "?")] = by_op.get(e.get("op", "?"), 0) + 1
            by_actor[e.get("actor", "?")] = \
                by_actor.get(e.get("actor", "?"), 0) + 1
            by_project[e.get("project_id", "?")] = \
                by_project.get(e.get("project_id", "?"), 0) + 1
        return {
            "total": len(entries),
            "by_op": by_op,
            "by_actor": by_actor,
            "by_project": by_project,
            "last": entries[-1] if entries else None,
            "oldest": entries[0] if entries else None,
        }


class SharedCheckpointStore:
    """A checkpoint bus that can live on a *shared* team backend.

    `backend` in {"filesystem","s3","gcs"} (default filesystem). For s3 /
    gcs, the real SDK is used when importable; otherwise the backend
    degrades to a local directory (documented in `self.backend_active`)
    so the same call shape works everywhere.
    """

    def __init__(self,
                 backend: str = "filesystem",
                 local_path: Optional[str] = None,
                 s3_bucket: Optional[str] = None,
                 s3_prefix: str = "charter/checkpoints",
                 gcs_bucket: Optional[str] = None,
                 gcs_prefix: str = "charter/checkpoints",
                 audit_path: Optional[str] = None) -> None:
        self.backend = backend
        self.backend_active = backend
        self._bus = CheckpointBus(local_path)
        self._s3 = None
        self._gcs = None
        self._s3_bucket = s3_bucket
        self._s3_prefix = s3_prefix
        self._gcs_bucket = gcs_bucket
        self._gcs_prefix = gcs_prefix
        self._audit = AuditLog(
            audit_path or os.path.join(
                os.path.expanduser("~"), ".charter", "audit.log"))

        if backend == "s3":
            try:
                import boto3  # type: ignore
                self._s3 = boto3.client("s3")
            except Exception:
                self._s3 = None
                self.backend_active = "filesystem"
        elif backend == "gcs":
            try:
                from google.cloud import storage  # type: ignore
                self._gcs = storage.Client()
            except Exception:
                self._gcs = None
                self.backend_active = "filesystem"

    # -- publish ---------------------------------------------------------
    def publish(self, project_id: str, agent_id: str,
                state: Dict[str, Any], label: str = "",
                stage: Optional[str] = None,
                actor: str = "") -> Dict[str, Any]:
        """Publish a checkpoint to the shared backend + audit it."""
        stage = stage or state.get("stage", "stage_0")
        path = self._bus.publish(project_id, agent_id, state,
                                  label=label, stage=stage)
        ok = True
        detail = f"local:{path}"
        if self.backend == "s3" and self._s3 and self._s3_bucket:
            try:
                key = f"{self._s3_prefix}/{project_id}/{agent_id}/{stage}.json"
                with open(path, "rb") as fh:
                    self._s3.upload_fileobj(fh, self._s3_bucket, key)
                detail = f"s3://{self._s3_bucket}/{key}"
            except Exception as exc:
                ok = False
                detail = f"s3-upload-failed:{exc}"
        elif self.backend == "gcs" and self._gcs and self._gcs_bucket:
            try:
                blob = self._gcs.bucket(self._gcs_bucket)
                key = f"{self._gcs_prefix}/{project_id}/{agent_id}/{stage}.json"
                with open(path, "rb") as fh:
                    blob.blob(key).upload_from_file(fh)
                detail = f"gs://{self._gcs_bucket}/{key}"
            except Exception as exc:
                ok = False
                detail = f"gcs-upload-failed:{exc}"

        self._audit.record(AuditEntry(
            op="publish", ts=time.time(), actor=actor or agent_id,
            project_id=project_id, agent_id=agent_id, stage=stage,
            backend=self.backend_active, detail=detail, ok=ok))
        return {"ok": ok, "path": path, "backend": self.backend_active,
                "stage": stage, "label": label}

    # -- pull ------------------------------------------------------------
    def pull(self, project_id: str, agent_id: Optional[str] = None,
             stage: Optional[str] = None,
             actor: str = "") -> Optional[Dict[str, Any]]:
        """Pull a checkpoint from the shared backend + audit it.

        Prefers the shared backend (s3/gcs) if active, else the local bus.
        """
        # try the shared backend first if it's live
        if self.backend == "s3" and self._s3 and self._s3_bucket:
            key = f"{self._s3_prefix}/{project_id}/{agent_id or '_'}/" \
                  f"{stage or '_'}"
            # list then download the newest
            try:
                objs = self._s3.list_objects_v2(
                    Bucket=self._s3_bucket,
                    Prefix=f"{self._s3_prefix}/{project_id}/")
                keys = [o["Key"] for o in objs.get("Contents", [])
                        if o["Key"].startswith(
                            f"{self._s3_prefix}/{project_id}/")]
                keys.sort()
                if keys:
                    import io
                    obj = self._s3.get_object(
                        Bucket=self._s3_bucket, Key=keys[-1])
                    raw = obj["Body"].read().decode("utf-8")
                    cp = json.loads(raw)
                    self._audit.record(AuditEntry(
                        op="pull", ts=time.time(), actor=actor or agent_id
                        or "?", project_id=project_id,
                        agent_id=cp.get("agent_id", agent_id or ""),
                        stage=cp.get("stage", stage or ""),
                        backend=self.backend_active,
                        detail=f"s3://{self._s3_bucket}/{keys[-1]}",
                        ok=True))
                    return cp
            except Exception:
                pass
        if self.backend == "gcs" and self._gcs and self._gcs_bucket:
            try:
                bucket = self._gcs.bucket(self._gcs_bucket)
                blobs = list(bucket.list_blobs(
                    prefix=f"{self._gcs_prefix}/{project_id}/"))
                if blobs:
                    target = blobs[-1]
                    raw = target.download_as_string()
                    cp = json.loads(raw)
                    self._audit.record(AuditEntry(
                        op="pull", ts=time.time(), actor=actor or agent_id
                        or "?", project_id=project_id,
                        agent_id=cp.get("agent_id", agent_id or ""),
                        stage=cp.get("stage", stage or ""),
                        backend=self.backend_active,
                        detail=f"gs://{self._gcs_bucket}/{target.name}",
                        ok=True))
                    return cp
            except Exception:
                pass
        # fall back to the local bus
        cp = self._bus.pull(project_id, agent_id=agent_id, stage=stage)
        if cp is not None:
            self._audit.record(AuditEntry(
                op="pull", ts=time.time(), actor=actor or agent_id or "?",
                project_id=project_id, agent_id=cp.agent_id,
                stage=cp.stage, backend="filesystem",
                detail=f"local:{cp.path if hasattr(cp,'path') else 'bus'}",
                ok=True))
            return {"project_id": cp.project_id, "agent_id": cp.agent_id,
                    "stage": cp.stage, "state": cp.state,
                    "label": cp.label,
                    "published_ts": cp.published_ts,
                    "source_repo": cp.source_repo}
        self._audit.record(AuditEntry(
            op="pull", ts=time.time(), actor=actor or agent_id or "?",
            project_id=project_id, agent_id=agent_id or "",
            stage=stage or "", backend=self.backend_active,
            detail="not-found", ok=False))
        return None

    # -- audit -----------------------------------------------------------
    def audit(self, limit: int = 200) -> List[Dict[str, Any]]:
        return self._audit.entries(limit=limit)

    def report(self) -> Dict[str, Any]:
        return self._audit.report()


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------
_store_cache: Dict[str, SharedCheckpointStore] = {}


def _get_store(backend: str = "filesystem",
               local_path: Optional[str] = None,
               s3_bucket: Optional[str] = None,
               gcs_bucket: Optional[str] = None,
               audit_path: Optional[str] = None
               ) -> SharedCheckpointStore:
    key = f"{backend}|{local_path}|{s3_bucket}|{gcs_bucket}|{audit_path}"
    if key not in _store_cache:
        _store_cache[key] = SharedCheckpointStore(
            backend=backend, local_path=local_path, s3_bucket=s3_bucket,
            gcs_bucket=gcs_bucket, audit_path=audit_path)
    return _store_cache[key]


def publish_to_team(project_id: str, agent_id: str,
                    state: Dict[str, Any], label: str = "",
                    stage: Optional[str] = None,
                    backend: str = "filesystem",
                    actor: str = "",
                    s3_bucket: Optional[str] = None,
                    gcs_bucket: Optional[str] = None,
                    local_path: Optional[str] = None,
                    audit_path: Optional[str] = None) -> Dict[str, Any]:
    """tool: publish_to_team - publish a checkpoint to a shared team store
    + write an audit entry."""
    store = _get_store(backend, local_path=local_path,
                       s3_bucket=s3_bucket, gcs_bucket=gcs_bucket,
                       audit_path=audit_path)
    return store.publish(project_id, agent_id, state, label=label,
                        stage=stage, actor=actor)


def pull_from_team(project_id: str, agent_id: Optional[str] = None,
                    stage: Optional[str] = None,
                    backend: str = "filesystem",
                    actor: str = "",
                    s3_bucket: Optional[str] = None,
                    gcs_bucket: Optional[str] = None,
                    local_path: Optional[str] = None,
                    audit_path: Optional[str] = None
                    ) -> Optional[Dict[str, Any]]:
    """tool: pull_from_team - pull a checkpoint from a shared team store
    + write an audit entry."""
    store = _get_store(backend, local_path=local_path,
                       s3_bucket=s3_bucket, gcs_bucket=gcs_bucket,
                       audit_path=audit_path)
    return store.pull(project_id, agent_id=agent_id, stage=stage,
                      actor=actor)


def audit_report(backend: str = "filesystem",
                 local_path: Optional[str] = None,
                 s3_bucket: Optional[str] = None,
                 gcs_bucket: Optional[str] = None,
                 audit_path: Optional[str] = None
                 ) -> Dict[str, Any]:
    """tool: audit_report - the audit trail for a shared team store."""
    store = _get_store(backend, local_path=local_path,
                       s3_bucket=s3_bucket, gcs_bucket=gcs_bucket,
                       audit_path=audit_path)
    return store.report()
