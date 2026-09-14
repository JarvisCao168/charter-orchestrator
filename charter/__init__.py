"""Charter Orchestrator - executable governance core.

v1.1.0 turned the v1.0 spec into runnable code. v2.0 adds the four
production layers: OpenTelemetry export + Grafana, agent cryptographic
identity (signed tool calls), vector memory (semantic recall), and an
industry SOP template marketplace.

Quick start:
    from charter import init_project, advance_stage, confirm_gate, query_status
    python -m charter.cli demo
"""
__version__ = "2.0.0"

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
from .observability import trace_operation, query_trace, TraceLogger
from .evaluation import evaluate_agent, FaultInjectionMatrix
from .memory import memory_recall, MemoryStore
# --- v2.0 additions ---
from .otel_export import (
    to_otlp_json, prometheus_text, GrafanaDashboard, export_project,
)
from .identity import (
    IdentityRegistry, issue_agent, sign_tool_call, verify_tool_call,
)
from .vector_memory import (
    VectorMemory, vector_recall, vector_remember, hash_embed,
)
from .templates import (
    list_templates, load_template, apply_template, BUILTIN_TEMPLATES,
)

__all__ = [
    # v1.1 core
    "init_project", "advance_stage", "confirm_gate", "query_status",
    "save_checkpoint", "restore_checkpoint",
    "execute_in_sandbox", "create_dropbox", "manage_task_lifecycle",
    "trigger_workflow", "create_chat_chain",
    "GuardrailsEngine", "TDDEnforcer", "enforce_tdd", "guardrails",
    "GATE_DEFINITIONS", "DEFENSE_LINES", "RULES",
    "trace_operation", "query_trace", "TraceLogger",
    "evaluate_agent", "FaultInjectionMatrix",
    "memory_recall", "MemoryStore",
    # v2.0
    "to_otlp_json", "prometheus_text", "GrafanaDashboard", "export_project",
    "IdentityRegistry", "issue_agent", "sign_tool_call", "verify_tool_call",
    "VectorMemory", "vector_recall", "vector_remember", "hash_embed",
    "list_templates", "load_template", "apply_template", "BUILTIN_TEMPLATES",
]
