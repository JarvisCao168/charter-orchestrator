"""Charter Orchestrator - executable governance core.

v1.1.0 turned the v1.0 spec into runnable code. v2.0 added OTel export,
agent cryptographic identity, vector memory, and an SOP template
marketplace. v2.1 hardens all four: real Grafana/Prometheus provisioning,
X.509+mTLS agent certs, LLM-embedding backends, and a template PR review flow.

Quick start:
    from charter import init_project, advance_stage, confirm_gate, query_status
    python -m charter.cli demo
"""
__version__ = "2.2.0"

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
import importlib.util
HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None
from .templates import (
    list_templates, load_template, apply_template, BUILTIN_TEMPLATES,
)
# --- v2.1 hardening ---
from .grafana import (
    prometheus_data_source, tempo_data_source, dashboard_json,
    prometheus_scrape_config, otlp_exporter_config, live_metrics_demo,
)
from .llm_embed import (
    AgnesEmbedder, OpenAIEmbedder, NullEmbedder, pick_embedder, Embedder,
)
from .template_pr import (
    TemplateMarketplace, TemplatePR, validate_template, render_pr,
    TemplateSpecError,
)
if HAS_CRYPTO:
    from .x509_identity import (
        AgentPKI, AgentCert, x509_issue, x509_sign, x509_verify,
        X509IdentityError,
    )

# --- v2.2 production linkages ---
from .llm_judge_online import (
    JudgeBackend, AgnesJudge, OpenAIJudge, OfflineJudge, make_judge,
    score_with_judge, JUDGE_SYSTEM,
)
from .session_store import SessionStore, DEFAULT_DB
from .trace_link import (
    TraceLink, JaegerPush, TempoPush, JaegerQuery,
    aggregate_traces, slo_summary,
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
    # v2.1
    "prometheus_data_source", "tempo_data_source", "dashboard_json",
    "prometheus_scrape_config", "otlp_exporter_config", "live_metrics_demo",
    "AgnesEmbedder", "OpenAIEmbedder", "NullEmbedder", "pick_embedder", "Embedder",
    "TemplateMarketplace", "TemplatePR", "validate_template", "render_pr",
    "TemplateSpecError",
    # v2.2
    "JudgeBackend", "AgnesJudge", "OpenAIJudge", "OfflineJudge",
    "make_judge", "score_with_judge", "JUDGE_SYSTEM",
    "SessionStore", "DEFAULT_DB",
    "TraceLink", "JaegerPush", "TempoPush", "JaegerQuery",
    "aggregate_traces", "slo_summary",
]
