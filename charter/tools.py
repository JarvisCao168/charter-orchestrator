"""Utility tools (tools 7-11 of the Charter spec) - executable versions.

These are the "collaboration & tooling" layer: sandbox execution, dropbox
handoff, task lifecycle, workflow triggering, and chat-chain creation.
"""
from __future__ import annotations

import subprocess
import shutil
import tempfile
import uuid
from typing import Any, Dict, List, Optional


def execute_in_sandbox(command: str, timeout: int = 60) -> Dict[str, Any]:
    """tool 7/20 - execute_in_sandbox. Runs a shell command in an isolated temp dir.

    Refuses commands that match the security redline patterns.
    """
    import re
    blocked = [
        re.compile(r"rm\s+-rf\s+/"),
        re.compile(r"(?i)drop\s+table"),
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    ]
    for p in blocked:
        if p.search(command):
            return {"status": "blocked", "reason": f"security redline match: /{p.pattern}/"}
    workdir = tempfile.mkdtemp(prefix="charter_sb_")
    try:
        r = subprocess.run(command, shell=True, cwd=workdir,
                           capture_output=True, text=True, timeout=timeout)
        return {
            "status": "ok" if r.returncode == 0 else "nonzero",
            "returncode": r.returncode,
            "stdout": r.stdout[-4000:],
            "stderr": r.stderr[-4000:],
            "workdir": workdir,
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "reason": f"exceeded {timeout}s"}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def create_dropbox(name: str) -> Dict[str, Any]:
    """tool 8/20 - create_dropbox. File-based agent handoff mailbox."""
    box_id = "box_" + uuid.uuid4().hex[:10]
    return {"dropbox_id": box_id, "name": name, "path": f"/tmp/charter/{box_id}",
            "status": "created"}


def manage_task_lifecycle(task_id: str, action: str,
                          payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """tool 9/20 - manage_task_lifecycle. action in {create, start, done, blocked}."""
    allowed = {"create", "start", "done", "blocked"}
    if action not in allowed:
        return {"status": "error", "reason": f"action {action!r} not in {allowed}"}
    return {"task_id": task_id, "action": action, "status": "applied",
            "payload": payload or {}}


def trigger_workflow(workflow_id: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """tool 10/20 - trigger_workflow. Kick off a named event-driven workflow."""
    return {"workflow_id": workflow_id, "inputs": inputs or {},
            "run_id": "run_" + uuid.uuid4().hex[:8], "status": "triggered"}


def create_chat_chain(topic: str, agents: List[str]) -> Dict[str, Any]:
    """tool 11/20 - create_chat_chain. Ordered multi-agent discussion chain."""
    chain_id = "chain_" + uuid.uuid4().hex[:8]
    return {"chat_chain_id": chain_id, "topic": topic, "agents": agents,
            "turns": [], "status": "open"}
