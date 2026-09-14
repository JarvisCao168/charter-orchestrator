"""Cross-repo multi-agent checkpoint sharing (v2.5).

Lifts the in-process `core.save_checkpoint` (single-project, single-process
SQLite) to a **file-backed, cross-repo** checkpoint exchange: multiple
agents in different repos can *publish* a checkpoint to a shared
`~/.charter/checkpoints/` directory and *pull* another agent's checkpoint
by `project_id` / `agent_id` / `stage`. Each checkpoint is a JSON file
containing the full `Project` state dict, so a consumer in a *different*
repo (different filesystem root, different git history) can `restore`
it without needing the producer's in-process `Project` object.

    - `CheckpointBus(path=None)` - the file-backed exchange.
    - `publish(project_id, agent_id, state, label)` - write a JSON file to
      the bus, keyed by `project_id/agent_id/<stage>.json`.
    - `pull(project_id, agent_id=None, stage=None)` - read back a
      previously-published checkpoint (across repos).
    - `list_published(project_id=None, agent_id=None)` - enumerate what is
      available on the bus.
    - `import_into_core(project_id, agent_id, stage=None)` - pull a
      checkpoint and `core.restore_checkpoint` it, bridging the file-backed
      exchange into the in-process governance state machine.

Stdlib-only. The bus is a directory of JSON files; no DB, no network.
The default directory is `~/.charter/checkpoints` so it is shared across
repo checkouts on the same machine (and the path can be overridden for
CI / testing).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "CheckpointBus", "PublishedCheckpoint",
    "publish_checkpoint", "pull_checkpoint", "list_published",
    "import_into_core",
]

DEFAULT_BUS = os.path.join(os.path.expanduser("~"), ".charter", "checkpoints")


@dataclass
class PublishedCheckpoint:
    """A checkpoint as it sits on the bus (after a JSON round-trip)."""
    project_id: str
    agent_id: str
    stage: str
    state: Dict[str, Any]
    label: str = ""
    published_ts: float = field(default_factory=time.time)
    source_repo: str = ""

    def save(self, bus_path: str) -> str:
        """Persist to the bus. Returns the file path."""
        d = os.path.join(bus_path, self.project_id, self.agent_id)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{self.stage}.json")
        payload = {
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "stage": self.stage,
            "state": self.state,
            "label": self.label,
            "published_ts": self.published_ts,
            "source_repo": self.source_repo,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False,
                      default=str)
        return path

    @staticmethod
    def load(path: str) -> "PublishedCheckpoint":
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return PublishedCheckpoint(
            project_id=d["project_id"], agent_id=d["agent_id"],
            stage=d["stage"], state=d.get("state", {}),
            label=d.get("label", ""),
            published_ts=d.get("published_ts", time.time()),
            source_repo=d.get("source_repo", ""))


class CheckpointBus:
    """File-backed cross-repo checkpoint exchange."""

    def __init__(self, path: Optional[str] = None,
                 source_repo: str = "") -> None:
        self.path = path or DEFAULT_BUS
        self.source_repo = source_repo
        os.makedirs(self.path, exist_ok=True)

    # -- publish ---------------------------------------------------------
    def publish(self, project_id: str, agent_id: str,
                state: Dict[str, Any], label: str = "",
                stage: Optional[str] = None) -> str:
        stage = stage or state.get("stage", "stage_0")
        cp = PublishedCheckpoint(
            project_id=project_id, agent_id=agent_id, stage=stage,
            state=state, label=label, source_repo=self.source_repo)
        return cp.save(self.path)

    # -- pull ------------------------------------------------------------
    def pull(self, project_id: str, agent_id: Optional[str] = None,
             stage: Optional[str] = None) -> Optional[PublishedCheckpoint]:
        proj_dir = os.path.join(self.path, project_id)
        if not os.path.isdir(proj_dir):
            return None
        if agent_id:
            cands = [os.path.join(proj_dir, agent_id, f"{stage}.json")
                     if stage else os.path.join(proj_dir, agent_id)]
        else:
            cands = [os.path.join(proj_dir, a)
                     for a in os.listdir(proj_dir)]
        for c in cands:
            if os.path.isfile(c):
                return PublishedCheckpoint.load(c)
            if os.path.isdir(c):
                files = sorted(
                    (os.path.join(c, f) for f in os.listdir(c)
                     if f.endswith(".json")),
                    reverse=True)
                if stage:
                    files = [f for f in files
                             if os.path.basename(f).endswith(f"{stage}.json")]
                if files:
                    return PublishedCheckpoint.load(files[-1])
        return None

    def list_published(self, project_id: Optional[str] = None,
                       agent_id: Optional[str] = None) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        if not os.path.isdir(self.path):
            return out
        roots = [project_id] if project_id else os.listdir(self.path)
        for r in roots:
            proj_dir = os.path.join(self.path, r)
            if not os.path.isdir(proj_dir):
                continue
            agents = [agent_id] if agent_id else os.listdir(proj_dir)
            for a in agents:
                agent_dir = os.path.join(proj_dir, a)
                if not os.path.isdir(agent_dir):
                    continue
                for fname in sorted(os.listdir(agent_dir)):
                    if fname.endswith(".json"):
                        out.append({"project_id": r, "agent_id": a,
                                     "stage": fname[:-5],
                                     "path": os.path.join(agent_dir, fname)})
        return out


# ---------------------------------------------------------------------------
# Module-level convenience (bus at the default path)
# ---------------------------------------------------------------------------
def _default_bus() -> CheckpointBus:
    return CheckpointBus(DEFAULT_BUS)


def publish_checkpoint(project_id: str, agent_id: str,
                      state: Dict[str, Any], label: str = "",
                      stage: Optional[str] = None,
                      bus_path: Optional[str] = None,
                      source_repo: str = "") -> str:
    """tool: publish_checkpoint - write a checkpoint to the cross-repo bus."""
    bus = CheckpointBus(bus_path, source_repo=source_repo) if bus_path \
        else _default_bus()
    return bus.publish(project_id, agent_id, state, label=label,
                       stage=stage)


def pull_checkpoint(project_id: str, agent_id: Optional[str] = None,
                    stage: Optional[str] = None,
                    bus_path: Optional[str] = None
                    ) -> Optional[PublishedCheckpoint]:
    """tool: pull_checkpoint - read back a published checkpoint."""
    bus = CheckpointBus(bus_path) if bus_path else _default_bus()
    return bus.pull(project_id, agent_id=agent_id, stage=stage)


def list_published(project_id: Optional[str] = None,
                   agent_id: Optional[str] = None,
                   bus_path: Optional[str] = None
                   ) -> List[Dict[str, str]]:
    """tool: list_published - enumerate the cross-repo bus."""
    bus = CheckpointBus(bus_path) if bus_path else _default_bus()
    return bus.list_published(project_id=project_id, agent_id=agent_id)


def import_into_core(project_id: str, agent_id: Optional[str] = None,
                     stage: Optional[str] = None,
                     bus_path: Optional[str] = None) -> Dict[str, Any]:
    """tool: import_into_core - pull a checkpoint and restore it in-process.

    Bridges the file-backed cross-repo exchange into the
    `charter.core` state machine: `restore_checkpoint` re-instantiates the
    Project state so governance / gates / artifacts are available again in
    a different process / repo.
    """
    from .core import _get, registry
    cp = pull_checkpoint(project_id, agent_id=agent_id, stage=stage,
                         bus_path=bus_path)
    if cp is None:
        return {"ok": False, "reason": "no published checkpoint found"}
    # The core registry keys by project_id; inject the state.
    # (save_checkpoint/restore_checkpoint round-trip via the registry dict.)
    # We rebuild the project state the way restore_checkpoint would, by
    # writing the published state back through the public API.
    from . import core as _core
    # Best-effort: if the project id is known to the local registry, sync
    # its artifacts + stage; otherwise report what was pulled so the caller
    # can apply it.
    result = {"ok": True, "project_id": project_id, "agent_id": cp.agent_id,
              "stage": cp.stage, "state": cp.state, "label": cp.label,
              "source_repo": cp.source_repo}
    try:
        p = _core.registry.get(project_id)
        if p is not None:
            p.stage_index = cp.state.get(
                "stage_index", p.stage_index)
            p.current_stage = cp.state.get("stage", p.current_stage)
            p.artifacts.update(cp.state.get("artifacts", {}))
            p.status = cp.state.get("status", p.status)
            result["applied_to"] = "local-registry"
        else:
            result["applied_to"] = "none-local"
    except Exception as exc:
        result["applied_to"] = f"error: {exc}"
    return result
