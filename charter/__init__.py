"""Charter Orchestrator - Executable governance core.

v1.1.0 turns the v1.0 specification into runnable code: a real orchestrator
with gate enforcement, TDD discipline, guardrails, checkpoints, tracing,
agent evaluation, and persistent memory.

Quick start:
    from charter import init_project, advance_stage, confirm_gate, query_status

See docs/quickstart.md for the full tour.
"""
__version__ = "1.1.0"

from .core import (
    init_project, advance_stage, confirm_gate, query_status,
    save_checkpoint, restore_checkpoint,
)
from .tools import (
    execute_in_sandbox, create_dropbox, manage_task_lifecycle,
    trigger_workflow, create_chat_chain,
)
from .governance import (
    GuardrailsEngine, TDDEnforcer, enforce_tdd, guardrails,
    GATE_DEFINITIONS, DEFENSE_LINES, RULES,
)
from .observability import trace_operation, query_trace
from .evaluation import evaluate_agent, FaultInjectionMatrix
from .memory import memory_recall, MemoryStore

__all__ = [
    "init_project", "advance_stage", "confirm_gate", "query_status",
    "save_checkpoint", "restore_checkpoint",
    "execute_in_sandbox", "create_dropbox", "manage_task_lifecycle",
    "trigger_workflow", "create_chat_chain",
    "GuardrailsEngine", "TDDEnforcer", "enforce_tdd", "guardrails",
    "GATE_DEFINITIONS", "DEFENSE_LINES", "RULES",
    "trace_operation", "query_trace",
    "evaluate_agent", "FaultInjectionMatrix",
    "memory_recall", "MemoryStore",
]
