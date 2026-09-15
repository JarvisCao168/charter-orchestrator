"""Charter Orchestrator - executable governance core.

v1.1.0 turned the v1.0 spec into runnable code. v2.0 added OTel export,
agent cryptographic identity, vector memory, and an SOP template
marketplace. v2.1 hardens all four: real Grafana/Prometheus provisioning,
X.509+mTLS agent certs, LLM-embedding backends, and a template PR review flow.

Quick start:
    from charter import init_project, advance_stage, confirm_gate, query_status
    python -m charter.cli demo
"""
__version__ = "2.6.0"

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

# --- v2.3 production linkages ---
from .mtls import (
    TrustAnchor, MTLSResult, MTLSConfig, verify_chain,
    verify_server_cert, build_mtls_session, mtls_check,
)
from .github_pr import TemplatePRBot, open_template_pr, PRResult
from .embed_cache import (
    EmbedCache, CachedEmbedder, production_embedder, embed_with_cache,
)
from .spiffe import (
    TrustDomain, SVID, SVIDBundle, build_spiffe_id, parse_spiffe_id,
    issue_svid, verify_svid, bundle_svid, SPIFFEError,
)

# --- v2.4 multi-system linkages ---
from .judge_consensus import (
    ConsensusJudge, consensus_judge, agreement_matrix,
)
from .memory_compress import (
    HeuristicSummarizer, LLMSummarizer, MemoryCompressor,
    compress_session, pick_summarizer,
)
from .slo_alerts import (
    AlertPayload, SLOAlertGate, build_alert_payload,
    fire_alertmanager, fire_pagerduty, fire,
)
from .spiffe_grpc import (
    RemoteSVID, SPIREGateway, connect_spire, fetch_x509_svid,
    verify_remote_svid,
)
from .pr_community import (
    TemplateCIGate, run_template_ci, ScoredTemplate,
    community_score, rank_templates, add_feedback,
    template_pr_with_ci,
)

# --- v2.5 multi-system linkages (phase 2) ---
from .judge_voting import (
    ProviderVote, WeightedVotingJudge, vote_judges, accuracy_weights,
)
from .memory_hierarchy import (
    TierSummary, MemoryHierarchy, compress_project, recall_project,
)
from .prometheus_rules import (
    alert_rules, alertmanager_provisioning, render_provisioning_bundle,
)
from .spiffe_attestation import (
    AttestationRequest, AttestResult, build_attestation_request,
    spire_attest, verify_attestation, ATTEST_TYPES,
)
from .pr_comment_scoring import (
    PRSignals, fetch_pr_signals, score_from_pr, auto_merge_gate,
)
from .cross_repo import (
    CheckpointBus, PublishedCheckpoint,
    publish_checkpoint, pull_checkpoint, list_published,
    import_into_core,
)

# --- v2.6 multi-system linkages (phase 3) ---
from .judge_concurrency import (
    vote_judges_concurrent, JudgeResultCache, cached_vote,
)
from .memory_clustering import (
    Cluster, MemoryClusterer, cluster_episodes, cluster_session,
    cluster_count,
)
from .mimir_multitenant import (
    mimir_tenants, tenant_rules, label_propagation_config,
    mimir_provisioning_bundle,
)
from .spire_k8s_mtls import (
    K8SSPIREAgentConfig, render_spire_agent_config,
    render_agent_values, mtls_env,
)
from .pr_sentiment import (
    CommentAnalysis, HeuristicCommentAnalyzer, LLMCommentAnalyzer,
    analyze_comment, analyze_pr_comments, pick_analyzer,
)
from .checkpoint_shared import (
    SharedCheckpointStore, AuditLog,
    publish_to_team, pull_from_team, audit_report,
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
    # v2.3
    "TrustAnchor", "MTLSResult", "MTLSConfig", "verify_chain",
    "verify_server_cert", "build_mtls_session", "mtls_check",
    "TemplatePRBot", "open_template_pr", "PRResult",
    "EmbedCache", "CachedEmbedder", "production_embedder", "embed_with_cache",
    "TrustDomain", "SVID", "SVIDBundle", "build_spiffe_id", "parse_spiffe_id",
    "issue_svid", "verify_svid", "bundle_svid", "SPIFFEError",
    # v2.4
    "ConsensusJudge", "consensus_judge", "agreement_matrix",
    "HeuristicSummarizer", "LLMSummarizer", "MemoryCompressor",
    "compress_session", "pick_summarizer",
    "AlertPayload", "SLOAlertGate", "build_alert_payload",
    "fire_alertmanager", "fire_pagerduty", "fire",
    "RemoteSVID", "SPIREGateway", "connect_spire", "fetch_x509_svid",
    "verify_remote_svid",
    "TemplateCIGate", "run_template_ci", "ScoredTemplate",
    "community_score", "rank_templates", "add_feedback",
    "template_pr_with_ci",
    # v2.5
    "ProviderVote", "WeightedVotingJudge", "vote_judges", "accuracy_weights",
    "TierSummary", "MemoryHierarchy", "compress_project", "recall_project",
    "alert_rules", "alertmanager_provisioning", "render_provisioning_bundle",
    "AttestationRequest", "AttestResult", "build_attestation_request",
    "spire_attest", "verify_attestation", "ATTEST_TYPES",
    "PRSignals", "fetch_pr_signals", "score_from_pr", "auto_merge_gate",
    "CheckpointBus", "PublishedCheckpoint", "publish_checkpoint",
    "pull_checkpoint", "list_published", "import_into_core",
    # v2.6
    "vote_judges_concurrent", "JudgeResultCache", "cached_vote",
    "Cluster", "MemoryClusterer", "cluster_episodes", "cluster_session",
    "cluster_count",
    "mimir_tenants", "tenant_rules", "label_propagation_config",
    "mimir_provisioning_bundle",
    "K8SSPIREAgentConfig", "render_spire_agent_config",
    "render_agent_values", "mtls_env",
    "CommentAnalysis", "HeuristicCommentAnalyzer", "LLMCommentAnalyzer",
    "analyze_comment", "analyze_pr_comments", "pick_analyzer",
    "SharedCheckpointStore", "AuditLog", "publish_to_team",
    "pull_from_team", "audit_report",
]
