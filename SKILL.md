# Charter Orchestrator — Skill Definition

> **Skill 名称**：Charter Orchestrator
> **Version**: 2.1.0
> **Charter / 章程**: 智能体团队协作章程（终极完整版）
> **Release / 发布**: 2026-09-14 v1.0.0 · 2026-09-15 v1.1.0 · 2026-09-15 v2.0.0 · 2026-09-15 v2.1.0 (hardened production)
> **许可证**：MIT
> **定位**：Agent之上的全链路治理与编排框架 —— 定义 Agent 怎么干活、干到什么标准、什么时候该停下来让人确认

---

## 一、概述 / Overview

Charter Orchestrator 是一个"治理+流程+工具"三位一体的智能体编排框架。它在整合 GitHub Squad、ChatDev、GitHub Agentic Workflows、OpenHands 等项目核心优势的基础上，经过对 LangGraph、CrewAI、AG2、OpenAI Agents SDK、autonomous-dev-team、agent-skills、Superpowers、Orchestrator 等 10+ 个同类项目的深度竞品分析，实现了从"流程编排框架"到"企业级智能体治理平台"的全面跃迁。

### 核心定位 / Core Positioning

> GitHub 上现有的 Agent 项目解决的是"怎么让 Agent 做事"（引擎/工具/执行），而 Charter Orchestrator 解决的是"怎么管理 Agent 做事"（治理/流程/规则）—— 它是 **Agent 之上的管理层**，而非 Agent 本身。
>
> Existing Agent projects on GitHub solve **how to make Agents do things** (engine/tool/execution). Charter Orchestrator solves **how to govern Agents doing things** (governance/process/rules) — it is **the management layer above Agents**, not the Agent itself.

### 架构总览 / Architecture (v1.0)

```
+------------------------------------------------------------------+
|                    Charter Orchestrator v1.0                     |
+------------------------------------------------------------------+
|  [可观测性层]  Trace/Span 全链路追踪 · 审计增强 · 指标暴露        |  <- 新增
+------------------------------------------------------------------+
|  [Guardrails层]  输入校验 · 输出过滤 · 安全护栏 · 合规审计        |  <- 新增
+------------------------------------------------------------------+
|  [Checkpoint层]  快照 · 回滚 · 分支 · 恢复                       |  <- 新增
+------------------------------------------------------------------+
|  [治理总纲]      角色分工 · 权限边界 · 沟通规范 · 安全红线        |
|                  · 代码质量 · Token预算 · 治理规则查询             |
+------------------------------------------------------------------+
|  [执行流程]      10阶段SOP · 门禁机制 · 阶段-Skill映射            |
|                  · 事件驱动 · 任务链 · 自动驾驶模式                |  <- 增强
+------------------------------------------------------------------+
|  [工具层]        6基础工具 + 9新增工具 + 6增强工具                |
|                  + CheckpointManager + ModelDispatcher            |  <- 新增
|                  + GuardrailsEngine + TDDEnforcer                 |  <- 新增
|                  + WorktreeManager + ObservabilityLayer           |  <- 新增
+------------------------------------------------------------------+
|  [制度层]        9类治理规则 + 4类新增规则                        |
|                  + Checkpoint规则 + Guardrails规则                |  <- 新增
|                  + TDD规则 + AutonomousMode规则                   |  <- 新增
+------------------------------------------------------------------+
```

### 能力跃迁一览 / Capability Jumps

| 跃迁能力 | 灵感来源 | 新增/增强工具 |
|----------|----------|---------------|
| Checkpoint 状态快照与恢复 | LangGraph | save_checkpoint / restore_checkpoint |
| 多模型调度层 | Orchestrator | dispatch_to_model |
| 工程技能深度扩展 | agent-skills | APIDesignPro / FrontendEngineer / DatabaseArchitect / SecurityAuditor / PerformanceEngineer / ArchitectureReviewer |
| TDD 强制纪律引擎 | Superpowers + autonomous-dev-team | enforce_tdd |
| Git Worktree 多环境隔离 | autonomous-dev-team | manage_worktree |
| Guardrails 安全护栏 | OpenAI Agents SDK | guardrails |
| 自动驾驶模式 | agent-skills | enable_autonomous_mode |
| 可观测性增强 | LangGraph + LangSmith | trace_operation / query_trace |

### 工具总数变化 / Tool Count Evolution

| 阶段 | 基础工具 | 新增工具 | 增强工具 | 总计 |
|------|----------|----------|----------|------|
| 早期预览 | 6 | — | — | 6 |
| 中期预览 | 6 | 5 | 4 | 11 |
| **v1.0（首次公开发布）** | 6 | 9 | 6 | 20 |

### Skills 总数变化 / Skills Count Evolution

| 分类 | 中期预览数量 | v1.0 新增 | v1.0 总计 |
|------|-----------|-----------|-----------|
| 环境与基础设施 | 4 | 3 | 7 |
| 分析与决策 | 4 | 2 | 6 |
| 开发与工程 | 6 | 6 | 12 |
| 测试与验证 | 3 | 2 | 5 |
| 交付与运维 | 3 | 1 | 4 |
| 协作与记忆 | 4 | 0 | 4 |
| 工具与版本控制 | 4 | 0 | 4 |
| 安全与治理 | 0 | 3 | 3 |
| 可观测性 | 0 | 2 | 2 |
| **合计** | **28** | **19** | **47** |

### 治理规则类别变化 / Rule Category Evolution

| 版本 | 治理规则类别数 | 新增规则 |
|------|---------------|----------|
| 中期预览 | 9类 | — |
| v1.0 | 13类 | Checkpoint状态管理规则、多模型调度规则、TDD纪律规则、Guardrails安全护栏规则 |

---

## 一·五、v1.1 可执行核心 / v1.1 Executable Core

v1.1 把 v1.0 的规范变成可运行代码。`charter/` 包提供真实实现，所有 P0 缺口已补齐：

| 模块 / Module | 能力 / Capability | 状态 / Status |
|------|------|------|
| `charter/core.py` | 10 阶段状态机 + 门禁 + Checkpoint 快照/回滚 | ✅ 可执行 |
| `charter/governance.py` | 13 类规则 + 6 道防线 + Guardrails + TDD 引擎 | ✅ 可执行 |
| `charter/observability.py` | 全链路 Trace（OTel 兼容） | ✅ 可执行 |
| `charter/evaluation.py` | LLM-as-judge 评估 + 14 类故障注入矩阵 | ✅ 可执行（P0 新增） |
| `charter/memory.py` | 跨会话 Agent 记忆（SQLite + 召回） | ✅ 可执行（P0 新增） |
| `charter/cli.py` | `python -m charter.cli demo` 5 分钟跑通 | ✅ 可执行 |
| `tests/` | 10 个可执行测试证明框架真能拦截违规 | ✅ 通过 |

**一键跑通 / One-liner:**
```bash
pip install -e . && python -m charter.cli demo
```

> v1.0 是"规范"（你读它、按它建团队）；v1.1 是"引擎"（你 `import charter` 直接跑）。
> v1.0 was the **spec**; v1.1 is the **engine**.

## 一·七、v2.0 生产层 / v2.0 Production Layers

v2.0 补齐同行测评中识别的 4 个生产缺口（Red Hat 2026 "7 missing capabilities" 对齐）：

| 模块 / Module | 能力 / Capability | 解决的缺口 / Gap Closed |
|------|------|------|
| `charter/otel_export.py` | OTLP/JSON 导出 + Prometheus 指标 + Grafana 仪表盘模板 | 可观测性 → 生产级（Red Hat #4） |
| `charter/identity.py` | Agent 加密身份 + HMAC 签名工具调用 + 防重放 + 能力边界 | 加密身份（Red Hat #1，同行最大缺口） |
| `charter/vector_memory.py` | 哈希嵌入向量记忆 + 语义召回（可插拔 LLM 嵌入后端） | 跨会话 Agent 记忆（全行业标配） |
| `charter/templates/` | 行业 SOP 模板市场（金融/医疗/电商/研究）+ 自定义发现 | 可复用行业治理基线 |

**新工具 / New tools (20 → 24):**
- `sign_tool_call` / `verify_tool_call`（加密身份）
- `vector_recall`（语义记忆召回）
- `load_template` / `apply_template`（SOP 模板）
- `export_project(fmt={otlp, prometheus, grafana})`（可观测性导出）

> v2.0 = 引擎 + 生产层。`pip install -e . && python -m charter.cli demo` 现在会连
> identity / vector / templates / OTel 一起跑通。
> v2.0 = engine + production layers. The demo now exercises all four new modules.

## 一·八、v2.1 强化 / v2.1 Hardening

v2.1 把 v2.0 的 4 个生产层从"能跑"升级到"生产级"：

| 升级项 / Upgrade | 模块 / Module | 说明 / Notes |
|------|------|------|
| **X.509 + mTLS 身份** | `charter/x509_identity.py` | 真实 X.509 Agent 证书（EC P-256 + CA 签发），ECDSA 签名工具调用，替换 v2.0 的 HMAC 方案；无 `cryptography` 时自动回退 HMAC |
| **真实 Grafana 数据源** | `charter/grafana.py` | Prometheus/Tempo 数据源 provisioning + 完整 dashboard + scrape 配置 + OTLP 导出器配置，可直接导入 Grafana |
| **LLM 嵌入后端** | `charter/llm_embed.py` | `AgnesEmbedder`/`OpenAIEmbedder` 接入 `VectorMemory(embed=...)`，语义召回从哈希嵌入升级为真实模型嵌入 |
| **模板市场 PR 流程** | `charter/template_pr.py` | `TemplateMarketplace` + `validate_template` + `render_pr`：行业模板走"提交 → 校验 → 审批 → 合并"治理流 |

**新增导出 / New exports**（`import charter` 可直接用）：
- `x509_issue / x509_sign / x509_verify`（X.509 Agent 身份，需 `pip install charter-orchestrator[crypto]`）
- `prometheus_data_source / tempo_data_source / dashboard_json / prometheus_scrape_config / live_metrics_demo`
- `AgnesEmbedder / OpenAIEmbedder / NullEmbedder / pick_embedder`
- `TemplateMarketplace / validate_template / render_pr`

> v2.1 = 生产加固。demo 现在连 X.509 签名调用 + Grafana provisioning + LLM 嵌入后端一起跑通。
> v2.1 = production hardening. The demo now exercises X.509 signed calls + Grafana provisioning + LLM embedder.

## 二、工具定义 / Tool Definitions

### 2.1 基础工具 / Base Tools (v1.0)

#### tool: init_project

- **描述**：初始化项目，创建项目工作区、配置基础环境、注册模型、注入 Guardrails 规则集。v1.0 增强：新增 Git Worktree 初始化、模型注册表配置、Guardrails 规则集注入。
- **灵感来源**：autonomous-dev-team + OpenAI Agents SDK
- **参数**：
  - `project_name` (string, 必填)：项目名称
  - `project_type` (string, 必填)：项目类型（software_dev / open_source_distillation / internal_tool / research）
  - `core_objective` (string, 必填)：核心目标描述
  - `team_size` (integer, 可选)：团队规模，默认 3
  - `checkpoint_enabled` (boolean, 可选)：是否启用 Checkpoint，默认 true
  - `guardrails_enabled` (boolean, 可选)：是否启用 Guardrails，默认 true
  - `tdd_enforcement` (string, 可选)：TDD 强制执行级别（off / soft / strict），默认 soft
  - `model_registry_path` (string, 可选)：模型注册表配置文件路径
  - `worktree_base_path` (string, 可选)：Worktree 基础路径
- **返回值**：project_id, workspace_path, initial_checkpoint_id, configured_models[], guardrails_status, worktree_path
- **适用阶段**：阶段〇
- **v1.0 变更**：新增 checkpoint_enabled、guardrails_enabled、tdd_enforcement、model_registry_path、worktree_base_path 参数

#### tool: advance_stage

- **描述**：推进项目到下一阶段。执行阶段前置检查、触发阶段 Skills、执行阶段任务、生成阶段产出物。v1.0 增强：新增 Checkpoint 自动创建、自动驾驶模式衔接、TDD 防线检查。
- **灵感来源**：LangGraph + Superpowers
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `target_stage` (string, 必填)：目标阶段标识（stage_0 ~ stage_9）
  - `checkpoint_before_advance` (boolean, 可选)：推进前是否自动创建 Checkpoint，默认 true
  - `autonomous_mode` (boolean, 可选)：是否在自动驾驶模式下推进，默认 false
  - `evidence` (object, 可选)：门禁校验证据（v1.0 增强：包含 Guardrails 校验结果）
- **返回值**：stage_id, stage_name, status, checkpoint_id, skills_triggered[], gate_results, next_stage_id
- **适用阶段**：全阶段
- **v1.0 变更**：新增 checkpoint_before_advance、autonomous_mode 参数；增强 evidence 参数支持 Guardrails 校验结果

#### tool: confirm_gate

- **描述**：执行门禁确认。检查上一阶段产出物质量、执行安全校验、记录审计日志。v1.0 增强：新增 6 道防线集成、Guardrails 校验结果作为证据。
- **灵感来源**：Superpowers + OpenAI Agents SDK
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `gate_id` (string, 必填)：门禁标识
  - `gate_type` (string, 必填)：门禁类型（manual / automatic / hybrid）
  - `evidence` (object, 必填)：校验证据（v1.0 增强：包含 Guardrails 校验结果、6道防线检查项）
  - `reviewer_id` (string, 可选)：审批人 ID（manual 类型必填）
  - `tdd_check` (object, 可选)：TDD 防线检查结果（v1.0 新增）
- **返回值**：gate_id, result (pass/fail/blocked), violations[], audit_log_id, recommendations
- **适用阶段**：全阶段门禁点
- **v1.0 变更**：新增 tdd_check 参数；增强 evidence 支持 Guardrails 校验结果；集成 6 道防线检查

#### tool: query_status

- **描述**：查询项目当前状态全貌。v1.0 增强：新增可观测性指标、Trace 聚合、健康度评分增强。
- **灵感来源**：LangSmith
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `detail_level` (string, 可选)：详细程度（basic / detailed / full），默认 detailed
  - `include_observability` (boolean, 可选)：是否包含可观测性指标，默认 true
  - `trace_aggregation` (boolean, 可选)：是否聚合 Trace 数据，默认 true
- **返回值**：project_id, current_stage, stage_progress, health_score, tools_status[], skills_status[], observability_metrics, trace_summary, gate_status
- **适用阶段**：全阶段
- **v1.0 变更**：新增 include_observability、trace_aggregation 参数；返回值新增 observability_metrics、trace_summary、health_score

#### tool: query_rule

- **描述**：运行时即时查询章程条款。智能体在执行过程中可随时查阅治理规则，相当于"边干活边翻法条"。
- **参数**：
  - `rule_category` (string, 可选)：规则类别（role_division / permission_boundary / communication_norm / safety_redline / code_quality / token_budget / checkpoint / model_dispatch / tdd / guardrails / all）
  - `rule_id` (string, 可选)：具体规则 ID
  - `context` (string, 可选)：查询上下文（用于上下文相关的规则匹配）
- **返回值**：rule_id, rule_category, rule_content, applicable_stages[], related_tools[], last_updated
- **适用阶段**：全阶段

#### tool: list_skills

- **描述**：列出当前项目可用的所有 Skills，支持按阶段、类别、触发方式筛选。
- **参数**：
  - `stage_filter` (string, 可选)：按阶段筛选（stage_0 ~ stage_9 / all）
  - `category_filter` (string, 可选)：按类别筛选
  - `trigger_filter` (string, 可选)：按触发方式筛选（manual / automatic / event_driven）
  - `active_only` (boolean, 可选)：是否仅显示已激活的 Skills，默认 false
- **返回值**：skills[], total_count, filters_applied
- **适用阶段**：全阶段

### 2.2 增强工具 / Enhanced Tools (v1.0)

#### tool: execute_in_sandbox

- **描述**：沙箱化代码执行。在隔离环境中执行代码，支持多模型调度接入和 Guardrails 输出过滤。v1.0 增强：新增 Worktree 目录绑定、多模型调度接入、Guardrails 输出过滤。
- **灵感来源**：OpenHands
- **参数**：
  - `code` (string, 必填)：要执行的代码
  - `language` (string, 必填)：编程语言
  - `worktree_path` (string, 可选)：Worktree 工作目录路径（v1.0 新增）
  - `model_id` (string, 可选)：指定使用的模型 ID（v1.0 新增）
  - `guardrails_output_filter` (boolean, 可选)：是否对输出执行 Guardrails 过滤，默认 true（v1.0 新增）
  - `timeout` (integer, 可选)：超时时间（秒），默认 120
  - `memory_limit` (string, 可选)：内存限制
- **返回值**：execution_id, stdout, stderr, exit_code, execution_time, model_used, guardrails_filtered, worktree_path
- **适用阶段**：阶段五到七
- **v1.0 变更**：新增 worktree_path、model_id、guardrails_output_filter 参数；返回值新增 model_used、guardrails_filtered、worktree_path

#### tool: create_dropbox

- **描述**：异步知识共享机制。借鉴 GitHub Squad 的 Drop-box 模式，实现团队间的异步知识共享和版本化文档协作。
- **灵感来源**：GitHub Squad
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `dropbox_name` (string, 必填)：Drop-box 名称
  - `content` (string, 必填)：共享内容
  - `version` (string, 可选)：版本号
  - `tags` (array, 可选)：标签列表
- **返回值**：dropbox_id, version, path, timestamp, contributors[]
- **适用阶段**：全阶段

#### tool: manage_task_lifecycle

- **描述**：任务生命周期管理。管理任务的创建、分配、执行、完成、归档等全生命周期状态。
- **灵感来源**：LobeHub
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `action` (string, 必填)：操作类型（create / assign / start / pause / resume / complete / archive / cancel）
  - `task_id` (string, 可选)：任务 ID（create 时不需要）
  - `task_params` (object, 可选)：任务参数（create 时必填）
- **返回值**：task_id, status, assigned_to, created_at, updated_at, history[]
- **适用阶段**：全阶段

#### tool: trigger_workflow

- **描述**：事件驱动工作流引擎。支持基于事件（Issue创建、PR事件、定时触发等）自动触发工作流执行。v1.0 增强：新增事件源增强校验、Guardrails 前置检查、Trace 注入。
- **灵感来源**：GitHub Agentic Workflows
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `workflow_id` (string, 必填)：工作流 ID
  - `event_source` (string, 必填)：事件源类型（issue / pr / timer / manual / webhook）
  - `event_payload` (object, 可选)：事件载荷
  - `guardrails_pre_check` (boolean, 可选)：是否执行 Guardrails 前置检查，默认 true（v1.0 新增）
  - `trace_parent_id` (string, 可选)：父级 Trace ID（v1.0 新增）
- **返回值**：workflow_run_id, status, triggered_at, stages_executed[], trace_id, guardrails_result
- **适用阶段**：全阶段
- **v1.0 变更**：新增 guardrails_pre_check、trace_parent_id 参数；返回值新增 guardrails_result、trace_id

#### tool: create_chat_chain

- **描述**：原子任务链生成。将复杂任务拆解为原子任务链，支持顺序执行、并行执行（Fan-out/Fan-in）和条件分支。
- **灵感来源**：ChatDev
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `chain_name` (string, 必填)：任务链名称
  - `tasks` (array, 必填)：任务列表，每个任务包含 id、type、params、depends_on
  - `execution_mode` (string, 可选)：执行模式（sequential / parallel / conditional），默认 sequential
- **返回值**：chain_id, status, tasks_executed[], result_summary
- **适用阶段**：全阶段

### 2.3 新增工具 / New Tools (v1.0)

#### tool: save_checkpoint

- **描述**：在任意节点（阶段内子任务完成时）创建状态快照，包含当前上下文、工具调用历史、产出物引用、Token消耗统计。v1.0 新增，灵感来源于 LangGraph Checkpoint 机制。
- **灵感来源**：LangGraph
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `checkpoint_name` (string, 必填)：快照名称
  - `stage` (string, 必填)：当前阶段标识
  - `node_id` (string, 可选)：节点 ID（阶段内子任务标识）
  - `metadata` (object, 可选)：自定义元数据
- **返回值**：checkpoint_id, snapshot_path, timestamp, stage, node_id, token_usage
- **适用阶段**：全阶段
- **治理规则**：受 Checkpoint 状态管理规则约束

#### tool: restore_checkpoint

- **描述**：恢复到指定快照状态，恢复上下文、工具状态、环境变量。v1.0 新增，灵感来源于 LangGraph Checkpoint 机制。
- **灵感来源**：LangGraph
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `checkpoint_id` (string, 必填)：快照 ID
  - `restore_mode` (string, 必填)：恢复模式（full / partial）
  - `target_node` (string, 可选)：目标节点（partial 模式下指定）
- **返回值**：restored_state, recovered_context, pending_tasks, restored_checkpoint_id, timestamp
- **适用阶段**：全阶段
- **治理规则**：受 Checkpoint 状态管理规则约束；仅 Hermes（调度中枢）和当前阶段主导智能体可执行

#### tool: dispatch_to_model

- **描述**：智能模型调度器，根据任务类型、复杂度、预算自动选择最优模型。支持 6+ 种 Runtime 实时发现、智能分配与降级。v1.0 新增，灵感来源于 Orchestrator 的多 Runtime 调度。
- **灵感来源**：Orchestrator (backnotprop)
- **参数**：
  - `task_type` (string, 必填)：任务类型（code / analysis / research / writing / review / test）
  - `complexity` (string, 必填)：复杂度等级（low / medium / high / critical）
  - `budget_tier` (string, 可选)：预算等级（free / standard / premium），默认 standard
  - `preferred_models` (array, 可选)：偏好模型列表（如 ["claude", "codex"]）
  - `fallback_models` (array, 可选)：备选模型列表
  - `project_id` (string, 可选)：项目 ID（用于成本追踪）
- **返回值**：model_assigned, execution_result, token_usage, fallback_triggered, cost_estimate, model_health_status
- **适用阶段**：全阶段
- **治理规则**：受多模型调度规则约束

#### tool: manage_worktree

- **描述**：基于 Git Worktree 的多环境隔离管理。为每个开发任务创建独立的工作区，确保并行开发零冲突。v1.0 新增，灵感来源于 autonomous-dev-team 的 Git Worktree 隔离。
- **灵感来源**：autonomous-dev-team
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `task_id` (string, 必填)：任务 ID
  - `base_branch` (string, 必填)：基础分支
  - `worktree_path` (string, 可选)：Worktree 路径（自动生成如果未指定）
  - `action` (string, 可选)：操作类型（create / use / merge / discard / cleanup），默认 create
- **返回值**：worktree_path, branch_name, status, created_at, git_hash
- **适用阶段**：阶段五到八
- **治理规则**：受 Git Worktree 隔离规则约束

#### tool: enforce_tdd

- **描述**：强制执行 TDD 红绿循环纪律。在代码编写前必须存在失败测试，代码通过后必须执行重构。v1.0 新增，灵感来源于 Superpowers 的 6道防线 + autonomous-dev-team 的 TDD 强制。
- **灵感来源**：Superpowers + autonomous-dev-team
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `module_path` (string, 必填)：模块路径
  - `test_scope` (string, 可选)：测试范围（unit / integration / e2e / all），默认 all
- **返回值**：tdd_cycle_status, red_passed, green_passed, refactor_done, coverage_report, code_smells[]
- **适用阶段**：阶段六
- **治理规则**：受 TDD 纪律规则约束；未通过时代码提交门禁自动阻断

#### tool: guardrails

- **描述**：运行时安全护栏引擎，对智能体输入和输出进行双向校验，防止越权操作和数据泄露。v1.0 新增，灵感来源于 OpenAI Agents SDK 的 Guardrails 机制。
- **灵感来源**：OpenAI Agents SDK
- **参数**：
  - `direction` (string, 必填)：校验方向（inbound / outbound / bidirectional）
  - `rule_set` (string, 必填)：规则集名称
  - `input_data` (string, 可选)：输入数据（inbound/bidirectional 时必填）
  - `output_data` (string, 可选)：输出数据（outbound/bidirectional 时必填）
  - `project_id` (string, 可选)：项目 ID（用于审计追踪）
- **返回值**：guard_result (pass/fail), violations[], sanitized_output, audit_log_id, alert_triggered
- **适用阶段**：全阶段
- **治理规则**：受 Guardrails 安全护栏规则约束；默认启用，不可关闭

#### tool: enable_autonomous_mode

- **描述**：启用自动驾驶模式，在一次人工审批后自主运行多个阶段，但在每个关键验证点保留自动检查。v1.0 新增，灵感来源于 agent-skills 的 /build auto 模式。
- **灵感来源**：agent-skills
- **参数**：
  - `project_id` (string, 必填)：项目 ID
  - `start_stage` (string, 必填)：起始阶段
  - `end_stage` (string, 必填)：结束阶段
  - `approval_level` (string, 必填)：审批级别（standard / elevated / critical）
  - `verification_strictness` (string, 可选)：验证严格程度（lenient / standard / strict），默认 standard
- **返回值**：mode_status (active/paused/stopped), stages_autorun[], interruptions[], final_report, audit_log_id
- **适用阶段**：阶段五到七
- **安全约束**：仅 software_dev 和 open_source_distillation 类型项目可启用；internal_tool 和 research 类型禁止启用；生产环境部署（阶段八）始终需要人工确认

#### tool: trace_operation

- **描述**：为工具调用创建 Trace/Span 追踪记录，支持嵌套追踪。v1.0 新增，灵感来源于 LangSmith 的 Trace/Span 追踪。
- **灵感来源**：LangSmith
- **参数**：
  - `operation_name` (string, 必填)：操作名称
  - `parent_trace_id` (string, 可选)：父级 Trace ID（嵌套追踪时使用）
  - `metadata` (object, 可选)：自定义元数据
  - `span_attributes` (object, 可选)：Span 属性键值对
- **返回值**：trace_id, span_id, start_timestamp, parent_trace_id
- **适用阶段**：全阶段

#### tool: query_trace

- **描述**：查询操作追踪记录，支持按 trace_id、时间范围、状态等维度检索。v1.0 新增，灵感来源于 LangSmith。
- **灵感来源**：LangSmith
- **参数**：
  - `trace_id` (string, 可选)：Trace ID（不指定则查询列表）
  - `time_range` (object, 可选)：时间范围（start / end）
  - `status_filter` (string, 可选)：状态过滤（success / failed / all）
  - `project_id` (string, 可选)：项目 ID
- **返回值**：trace_tree (含所有 Span 的耗时、状态、错误信息), total_count, query_metadata
- **适用阶段**：全阶段

---

## 三、10阶段全链路SOP / 10-Stage SOP

### Stage 0: Baseline Investigation / 阶段〇：基础条件调查

- **目标**：环境探测、模型注册表发现、Guardrails 基线配置、项目初始化
- **核心工具**：init_project、dispatch_to_model、guardrails、manage_worktree、ModelRegistryProbe、GuardrailsBaseline
- **门禁**：基础环境就绪确认
- **产出物**：项目工作区、模型注册表、Guardrails 基线配置、初始 Checkpoint

### Stage 1: Problem Analysis & Feasibility / 阶段一：问题分析与可行性

- **目标**：竞品分析、技术可行性评估、风险评估、可行性报告
- **核心工具**：query_rule、query_status、save_checkpoint
- **门禁**：可行性基线确认
- **产出物**：竞品分析报告、可行性报告、可行性基线快照

### Stage 2: Requirement Refinement / 阶段二：需求提炼与功能定义

- **目标**：需求规格定义、功能边界划定、验收标准制定、需求基线锁定
- **核心工具**：query_rule、list_skills、enforce_tdd（部分 - 需求可测试性检查）
- **门禁**：需求可测试性检查（防线1：需求澄清）
- **产出物**：需求规格说明书、验收标准清单、需求基线

### Stage 3: Open-Source Distillation / 阶段三：开源蒸馏决策

- **目标**：开源组件选型、合规审计、复杂度分析、蒸馏决策、依赖兼容性检查
- **核心工具**：query_rule、dispatch_to_model（模型成本评估）
- **门禁**：蒸馏决策合规确认
- **产出物**：开源组件清单、合规审计报告、蒸馏决策文档、依赖兼容性报告

### Stage 4: Architecture & Tech Selection / 阶段四：架构设计与技术选型

- **目标**：系统架构设计、技术栈选型、接口设计、架构评审
- **核心工具**：guardrails、ArchitectureReviewer（自动激活）
- **门禁**：架构设计文档签字锁定（防线2：文档固化）
- **产出物**：架构设计文档、技术选型报告、接口规范、架构评审报告

### Stage 5: Dev Environment Setup / 阶段五：开发环境搭建

- **目标**：开发环境配置、Git Worktree 创建、TDD 环境配置、依赖安装验证
- **核心工具**：manage_worktree、enforce_tdd、WorktreeProvisioner、TDDSetup
- **门禁**：开发环境就绪确认
- **产出物**：隔离开发环境、TDD 配置、环境验证报告

### Stage 6: Modular Development / 阶段六：模块化开发

- **目标**：模块编码实现、TDD 红绿循环执行、代码审查、质量门禁
- **核心工具**：enforce_tdd、guardrails、enable_autonomous_mode、TDDEnforcer、SecurityAuditor、PerformanceEngineer
- **门禁**：6道防线全通过（需求澄清→文档固化→人类审批→分支隔离→TDD红绿→发版自检）
- **产出物**：源代码、测试用例、代码审查报告、TDD 执行记录、安全扫描报告

### Stage 7: Integration Testing & Acceptance / 阶段七：集成测试与验收

- **目标**：集成测试执行、性能基准测试、验收测试、问题修复验证
- **核心工具**：trace_operation、PerformanceBaseline、PerformanceEngineer
- **门禁**：测试通过率确认
- **产出物**：测试报告、性能基准报告、验收确认书、Trace 分析报告

### Stage 8: Packaging & Delivery / 阶段八：封装交付

- **目标**：版本封装、部署准备、安全审计、发布检查、部署执行
- **核心工具**：guardrails（最终检查）、SecurityAuditFinal、trace_operation
- **门禁**：发布前全量检查清单通过（防线6：发版自检）
- **产出物**：发布包、部署文档、安全审计报告、Guardrails 合规报告

### Stage 9: Retrospective & Knowledge / 阶段九：复盘与沉淀

- **目标**：项目复盘、知识沉淀、效率指标分析、可观测性报告生成
- **核心工具**：query_trace、ObservabilityReport
- **门禁**：复盘报告确认
- **产出物**：复盘报告、知识沉淀文档、可观测性报告、效率指标分析报告

---

## 四、阶段-技能映射 / Stage-Skill Mapping (v1.0, 47 Skills)

> v1.0 起，47 个 Skill 全部**文件化**，每个 Skill 拥有独立目录与 `SKILL.md`（含输入/输出契约、调用工具、治理约束）。
> Since v1.0, all 47 Skills are **file-based** — each has its own directory with `SKILL.md` (I/O contract + tool invocations + governance constraints).
> 根级目录索引见 [`skills/README.md`](skills/README.md)，机器可读清单见 [`skills/manifest.json`](skills/manifest.json)。
> 下文保留各分类的 ID 速查表；详细契约点击对应 Skill 目录。

### 4.1 环境与基础设施 / Environment (7) → `skills/env/`

`env_01` EnvironmentProbe · `env_02` SandboxProvisioner · `env_03` ModelRegistryProbe · `env_04` GuardrailsBaseline · `env_05` WorktreeProvisioner · `env_06` TDDSetup · `env_07` DependencyManager

### 4.2 分析与决策 / Analysis (6) → `skills/analysis/`

`analysis_01` CompetitorAnalyzer · `analysis_02` FeasibilityAssessor · `analysis_03` RiskAssessor · `analysis_04` DistillationDecider · `analysis_05` ArchitectureReviewer · `analysis_06` CostOptimizer

### 4.3 开发与工程 / Development (12) → `skills/dev/`

`dev_01` CodeGenerator · `dev_02` APIDesignPro · `dev_03` FrontendEngineer · `dev_04` DatabaseArchitect · `dev_05` CodeReviewer · `dev_06` SecurityAuditor · `dev_07` PerformanceEngineer · `dev_08` TDDEnforcer · `dev_09` TechDebtTracker · `dev_10` RefactoringAssistant · `dev_11` SBOMGenerator · `dev_12` BuildPipeline

### 4.4 测试与验证 / Testing (5) → `skills/test/`

`test_01` TestPlanner · `test_02` TestExecutor · `test_03` PerformanceBaseline · `test_04` SecurityTest · `test_05` AcceptanceValidator

### 4.5 交付与运维 / Delivery (4) → `skills/deploy/`

`deploy_01` ReleaseManager · `deploy_02` SecurityAuditFinal · `deploy_03` DeploymentOrchestrator · `deploy_04` RollbackManager

### 4.6 协作与记忆 / Collaboration (4) → `skills/collab/`

`collab_01` DropBoxManager · `collab_02` TaskChainOrchestrator · `collab_03` MeetingRecorder · `collab_04` KnowledgeGraph

### 4.7 工具与版本控制 / Tools (4) → `skills/tool/`

`tool_01` GitWorkflow · `tool_02` CI_CDPipeline · `tool_03` VersionManager · `tool_04` ConfigManager

### 4.8 安全与治理 / Security (3) → `skills/security/`

`security_01` GuardrailsEngine · `security_02` AuditLogger · `security_03` ComplianceChecker

### 4.9 可观测性 / Observability (2) → `skills/obs/`

`obs_01` TraceCollector · `obs_02` ObservabilityReport

> **校验**：每个 Skill 的输入/输出、调用工具（20 个之一）与治理约束（13 类之一）定义在其目录 `SKILL.md` 内。
> 机器可读一致性由 `scripts/validate_skills.py` 校验（确保 47 个文件齐全、引用工具/规则均存在）。

## 五、治理规则体系 / Governance Rules (v1.0, 13 categories)

### 5.1 角色分工规则 / Role Assignment

- **角色定义**：Hermes（调度中枢）、Architect（架构师）、Developer（开发者）、Tester（测试员）、Reviewer（审查员）
- **v1.0 增强**：新增 Model Dispatcher（模型调度员）角色定义，负责模型选择、调度、降级决策
- **权限边界**：每个角色有明确的能力域和操作权限，越权操作被 Guardrails 拦截

### 5.2 权限边界规则 / Permission Boundary

- **操作权限**：基于角色的操作权限矩阵
- **v1.0 增强**：新增 Guardrails 权限校验维度，运行时动态校验操作合法性
- **数据权限**：基于项目/阶段的數據访问控制

### 5.3 沟通规范规则 / Communication Protocol

- **沟通协议**：结构化沟通模板、状态更新规范、异常上报流程
- **会议规范**：站会/评审会/复盘会的结构与产出物要求

### 5.4 安全红线规则 / Security Redline

- **绝对禁止**：代码注入、敏感数据泄露、未授权访问、绕过门禁
- **v1.0 增强**：新增自动驾驶模式安全约束、Checkpoint 操作审计要求
- **违规处置**：自动拦截→告警→人工介入→审计记录

### 5.5 代码质量规则 / Code Quality

- **编码规范**：统一编码风格、命名规范、注释要求
- **v1.0 增强**：新增 TDD 红绿循环检查、技术债务管理要求
- **审查标准**：代码审查清单、质量门槛（覆盖率/复杂度/重复率）

### 5.6 Token 预算规则 / Token Budget

- **预算管控**：项目级/阶段级 Token 预算分配
- **v1.0 增强**：新增多模型分级计价、成本异常检测
- **超预算处置**：预警→限流→暂停→人工审批

### 5.7 治理规则查询规则 / Rule Query

- **查询接口**：query_rule 工具运行时即时查询
- **规则版本**：规则变更追踪与版本管理
- **上下文感知**：基于当前阶段/任务上下文的规则推荐

### 5.8 Checkpoint 状态管理规则 / Checkpoint State Mgmt (new)

- **快照策略**：每个阶段门禁通过时自动创建 checkpoint；关键决策点可手动创建
- **保留策略**：默认保留最近 10 个 checkpoint，可配置保留数量和 TTL
- **恢复权限**：仅 Hermes（调度中枢）和当前阶段主导智能体可执行恢复操作
- **审计要求**：所有 checkpoint 创建/恢复操作记录到审计日志，包含操作人、时间、快照摘要

### 5.9 多模型调度规则 / Multi-Model Dispatch (new)

- **模型发现**：运行时动态发现可用模型 Runtime，不维护静态列表
- **分配策略**：基于任务类型标签自动匹配最优模型
- **降级规则**：主模型不可用时自动降级到备选模型，降级事件需记录
- **成本管控**：不同模型分级计价，高成本模型调用需额外审批
- **偏好配置**：通过 PREFERENCES.md 定义项目级模型分配策略

### 5.10 TDD 纪律规则 / TDD Discipline (new)

- **强制红绿循环**：阶段六内所有代码提交必须经过 Red→Green→Refactor 循环
- **测试覆盖率门槛**：新代码行覆盖率不低于 80%，分支覆盖率不低于 60%
- **禁止跳过**：enforce_tdd 未通过时，代码提交门禁自动阻断
- **技术债务追踪**：自动识别代码异味（code smell）并记录到技术债务清单
- **重构审批**：大规模重构（变更文件数 > 20）需人工确认

### 5.11 Guardrails 安全护栏规则 / Guardrails (new)

- **默认启用**：所有项目的 inbound/outbound 护栏默认启用，不可关闭
- **敏感数据清单**：可配置敏感数据模式（API Key、密码、Token 等）自动脱敏
- **拦截告警**：高危拦截事件实时告警，中危拦截记录到审计日志
- **白名单机制**：允许配置特定模式豁免（如测试用例中的模拟密钥）
- **合规报告**：定期生成 Guardrails 合规报告，统计拦截率和趋势

### 5.12 自动驾驶模式规则 / Autonomous Mode (new)

- **启用条件**：仅 software_dev 和 open_source_distillation 类型项目可启用
- **禁止场景**：internal_tool 和 research 类型禁止启用
- **人工保留点**：生产环境部署（阶段八）始终需要人工确认
- **时长限制**：可配置最大自动运行时长（默认 4 小时）
- **审计要求**：所有自动操作完整审计记录

### 5.13 事件驱动规则 / Event-Driven

- **事件源**：Issue创建、PR事件、定时触发、Webhook
- **执行策略**：事件触发→规则匹配→工作流执行→结果通知
- **安全约束**：事件源验证、权限校验、防重放攻击

---

## 六、6道防线机制 / 6 Defense Lines (v1.0)

在门禁机制基础上，阶段六（模块化开发）新增 6 道防线：

| 防线 | 检查项 | 执行时机 | 失败处置 |
|------|--------|----------|----------|
| 防线1：需求澄清 | 需求是否已转化为可测试的验收标准 | 阶段二到三 | 返回阶段二补充 |
| 防线2：文档固化 | 架构设计文档是否已签字锁定 | 阶段四门禁 | 阻断，要求补充文档 |
| 防线3：人类审批 | 关键架构决策是否经人工确认 | 阶段五门禁 | 暂停，等待人工审批 |
| 防线4：分支隔离 | 是否在工作区隔离环境中开发 | 阶段六入口 | 自动创建 Worktree |
| 防线5：TDD红绿 | 是否遵循红-绿-重构循环 | 每次代码提交 | 阻断，要求补测试 |
| 防线6：发版自检 | 发布前全量检查清单是否通过 | 阶段八门禁 | 阻断，列出未通过项 |

---

## 七、自动驾驶模式 / Autonomous Mode (v1.0)

### 流程定义 / Flow Definition

```
启动自动驾驶模式（人工审批一次）
    |
    v
阶段五：开发环境搭建（自动验证）
    |
    v
阶段六：模块化开发（TDD强制 + 自动门禁）
    |   |-- 每个模块：Red->Green->Refactor 自动执行
    |   |-- 门禁自动检查（代码质量/安全/测试覆盖）
    |   '-- 失败时暂停并请求人工介入
    |
    v
阶段七：集成测试（自动执行 + Trace分析）
    |
    v
[高风险操作检查点] <- 生产部署仍需人工确认
    |
    v
阶段八：封装交付（自动封装 + Guardrails检查）
    |
    v
生成自动驾驶报告（含所有自动操作审计日志）
```

### 安全约束 / Safety Constraints

- 仅 software_dev 和 open_source_distillation 类型项目可启用
- internal_tool 和 research 类型禁止启用
- 生产环境部署（阶段八）始终需要人工确认
- 可配置最大自动运行时长（默认 4 小时）
- 所有自动操作完整审计记录

---

## 八、外部集成增强 / External Integrations

### 8.1 与 LangGraph 集成

- **集成方式**：通过 save_checkpoint/restore_checkpoint 工具对接 LangGraph 的 Checkpoint 持久化层
- **互补价值**：获得图状态机的任意节点快照/回滚能力，同时保持 v1.0 的治理规则体系
- **适用场景**：需要精细状态控制的复杂多阶段项目
- **参考项目**：https://github.com/langchain-ai/langgraph

### 8.2 与 CrewAI 集成

- **集成方式**：通过角色化任务分配增强，对接 CrewAI 的 Role-Task-Crew 抽象
- **互补价值**：获得灵活的角色化任务分配能力，同时通过 v1.0 的治理规则确保流程规范
- **适用场景**：需要灵活角色协作的多 Agent 项目
- **参考项目**：https://github.com/crewai-inc/crewai

### 8.3 与 AG2 集成

- **集成方式**：通过可选的 ConversationMode 开关，对接 AG2 的多 Agent 自由对话能力
- **互补价值**：获得 Agent 间自由讨论/辩论/共识的能力，适用于需要创造性探索的场景
- **适用场景**：需要多 Agent 讨论共识的研究型任务
- **参考项目**：https://github.com/ag2ai/ag2

### 8.4 与 OpenAI Agents SDK 集成

- **集成方式**：通过 guardrails 工具对接 OpenAI Guardrails 安全护栏
- **互补价值**：获得成熟的输入/输出双向校验能力
- **适用场景**：对安全性要求高的项目
- **参考项目**：https://github.com/openai/openai-agents-sdk

### 8.5 与 GitHub Squad 集成

- **集成方式**：通过 create_dropbox 工具对接 Squad 的 Drop-box 知识共享模式
- **互补价值**：获得仓库原生知识共享+独立审查机制
- **适用场景**：基于 GitHub 仓库的多 Agent 协作开发
- **参考项目**：https://github.com/bradygaster/squad

### 8.6 与 GitHub Agentic Workflows 集成

- **集成方式**：通过 trigger_workflow 工具对接 GitHub Actions 事件驱动工作流
- **互补价值**：获得 GitHub 原生集成+沙箱安全模型+多AI引擎支持
- **适用场景**：与 GitHub PR/Issue/CI/CD 深度集成的自动化流程
- **参考项目**：https://docs.github.com/actions

### 8.7 与 autonomous-dev-team 集成

- **集成方式**：通过 manage_worktree 工具对接 Git Worktree 隔离机制
- **互补价值**：获得多任务并行开发的零冲突工作区隔离
- **适用场景**：多模块并行开发的中型以上项目
- **参考项目**：https://github.com/zxkane/autonomous-dev-team

### 8.8 与 agent-skills 集成

- **集成方式**：将 agent-skills 的工程领域 Skills（API设计、前端工程、测试等）纳入 v1.0 的 Skill Registry
- **互补价值**：补充工程技能深度，同时通过 v1.0 的治理规则确保工程质量
- **适用场景**：需要专业工程能力的项目
- **参考项目**：https://github.com/addyosmani/agent-skills

### 8.9 与 Orchestrator 集成

- **集成方式**：通过 dispatch_to_model 工具对接 Orchestrator 的多 Runtime 调度层
- **互补价值**：获得 6+ 种 AI 模型 Runtime 的实时发现、智能分配与自动降级能力
- **适用场景**：需要多模型协作的复杂开发任务
- **参考项目**：https://github.com/backnotprop/orchestrator

### 8.10 与 Superpowers 集成

- **集成方式**：通过 enforce_tdd 工具对接 Superpowers 的 6道防线和 TDD 纪律
- **互补价值**：强化开发纪律，防止 AI "偷懒"跳过测试
- **适用场景**：对代码质量要求高的生产级项目
- **参考项目**：https://github.com/obra/superpowers

### 8.11 与 LangSmith 集成

- **集成方式**：通过 trace_operation/query_trace 工具对接 LangSmith 可观测性平台
- **互补价值**：获得生产级的 Trace/Span 追踪和调试能力
- **适用场景**：需要精细化运维监控的生产环境
- **参考项目**：https://smith.langchain.com

---

## 九、配置参考 / Configuration Reference

### 9.1 模型注册表配置（model_registry.json）

```json
{
  "runtimes": [
    {"name": "claude-code", "type": "claude", "health_endpoint": "..."},
    {"name": "codex", "type": "codex", "health_endpoint": "..."},
    {"name": "copilot", "type": "copilot", "health_endpoint": "..."},
    {"name": "deepseek", "type": "deepseek", "health_endpoint": "..."},
    {"name": "gemini", "type": "gemini", "health_endpoint": "..."},
    {"name": "grok", "type": "grok", "health_endpoint": "..."}
  ],
  "default_fallback": "claude",
  "cost_tracking": true
}
```

### 9.2 偏好配置（PREFERENCES.md）

```markdown
# 模型分配偏好
## 阶段模型偏好
- 阶段一（分析）: claude
- 阶段三（蒸馏）: deepseek
- 阶段六（开发）: codex
- 阶段七（测试）: claude

## 降级策略
- 主模型不可用 -> 备选模型 -> 轻量模型
- 降级事件记录到审计日志

## TDD 纪律
- tdd_enforcement: strict

## 自动驾驶模式
- 允许项目类型: [software_dev, open_source_distillation]
- 最大自动运行时长: 4h
- 高风险操作始终人工确认: true
```

---

## 十、兼容性说明 / Compatibility

v1.0 为首次公开发布版本，包含以下全量能力：

- 20 个编排工具（6 基础 + 9 新增 + 6 增强），接口向后兼容早期预览版
- 47 个 Skills（9 大分类），阶段-Skill 映射完整
- 13 类治理规则，覆盖角色分工到安全护栏
- 10 阶段全链路 SOP + 6 道防线 + 硬门禁机制
- 早期预览版的项目状态文件可直接被 v1.0 读取

### 10.1 升级建议

早期预览版用户升级到 v1.0 只需替换 SKILL.md 文件，无需修改项目状态文件格式。


## 十一、版本信息与路线图 / Version & Roadmap

### 11.1 版本演进 / Version History

| 版本 | 状态 | 核心内容 |
|------|------|----------|
| v1.0.0 | **当前版本（首版发布）** | 20工具 · 47 Skills · 13类治理规则 · 10阶段SOP · Checkpoint快照恢复 · 多模型调度 · TDD纪律 · Guardrails护栏 · 自动驾驶模式 · 可观测性追踪 |
| v1.1.0 | 规划 | 社区模板市场、多仓库协作、自定义阶段模板 |
| v2.0.0 | 愿景 | 自进化治理规则、跨项目知识图谱、AI驱动的流程优化 |

### 11.2 v1.0.0 变更日志 / Changelog

| 变更类型 | 变更内容 | 灵感来源 |
|----------|----------|----------|
| 新增工具 | save_checkpoint / restore_checkpoint - 状态快照与恢复 | LangGraph |
| 新增工具 | dispatch_to_model - 智能模型调度与降级 | Orchestrator |
| 新增工具 | manage_worktree - Git Worktree 多环境隔离 | autonomous-dev-team |
| 新增工具 | enforce_tdd - TDD 红绿循环强制纪律 | Superpowers |
| 新增工具 | guardrails - 输入/输出安全护栏 | OpenAI Agents SDK |
| 新增工具 | enable_autonomous_mode - 一次审批自动驾驶 | agent-skills |
| 新增工具 | trace_operation / query_trace - 操作追踪与分析 | LangSmith |
| 新增 Skill | APIDesignPro, FrontendEngineer, DatabaseArchitect, SecurityAuditor, PerformanceEngineer, ArchitectureReviewer | agent-skills |
| 增强工具 | init_project 新增 Worktree/模型注册表/Guardrails 配置 | 综合 |
| 增强工具 | advance_stage 新增 Checkpoint 自动创建/TDD防线检查 | LangGraph + Superpowers |
| 增强工具 | confirm_gate 新增6道防线集成 | Superpowers |
| 增强工具 | query_status 新增可观测性指标 | LangSmith |
| 增强工具 | execute_in_sandbox 新增 Worktree绑定/多模型接入/Guardrails过滤 | 综合 |
| 增强工具 | trigger_workflow 新增事件源增强/Guardrails前置 | GitHub Agentic Workflows |
| 新增规则 | Checkpoint状态管理规则 | LangGraph |
| 新增规则 | 多模型调度规则 | Orchestrator |
| 新增规则 | TDD纪律规则 | Superpowers |
| 新增规则 | Guardrails安全护栏规则 | OpenAI Agents SDK |
| 新增章节 | 自动驾驶模式流程定义 | agent-skills |
| 新增章节 | 外部集成增强（LangGraph/CrewAI/AG2/OpenAI SDK/Squad/Agentic Workflows/autonomous-dev-team/agent-skills/Orchestrator/Superpowers/LangSmith） | 竞品分析 |


---


### v2.2 路线图 / v2.2 Roadmap（v2.1 已实现 4 项强化）

**v2.0 已实现 / v2.0 Shipped:**
- ✅ OTel 导出 + Prometheus + Grafana 仪表盘（`charter/otel_export.py`）
- ✅ Agent 加密身份 + 签名工具调用 + 防重放（`charter/identity.py`）
- ✅ 向量记忆 + 语义召回（`charter/vector_memory.py`，哈希嵌入，可插拔 LLM）
- ✅ 行业 SOP 模板市场（`charter/templates/`：finance/healthcare/e-commerce/research）

**v2.1 已实现 / v2.1 Shipped:**
- ✅ X.509 Agent 证书 + ECDSA 签名工具调用（`charter/x509_identity.py`，可选 crypto extra）
- ✅ 真实 Grafana 数据源 provisioning（`charter/grafana.py`）
- ✅ LLM 嵌入后端 Agnes/OpenAI（`charter/llm_embed.py`，接入 VectorMemory）
- ✅ 行业模板 PR 治理流（`charter/template_pr.py`）

**v2.2 已实现 / v2.2 Shipped:**
- ✅ 在线 LLM-as-judge（`charter/llm_judge_online.py`，Agnes/OpenAI 后端 + 离线 fallback）
- ✅ 跨会话持久化记忆（`charter/session_store.py`，SQLite WAL，语义召回，跨进程安全）
- ✅ OTel → Jaeger/Tempo 完整链路（`charter/trace_link.py`，重试安全导出 + 查询 + SLO 摘要）

**v2.3 已实现 / v2.3 Shipped:**
- ✅ 真实 mTLS 双向认证（`charter/mtls.py`，server 侧证书链校验 + 吊销 + CA 签名）
- ✅ 模板市场自动开 GitHub PR（`charter/github_pr.py`，离线安全草稿 fallback）
- ✅ LLM 嵌入生产 endpoint + LRU/磁盘缓存（`charter/embed_cache.py`）
- ✅ PKI/SPIFFE 身份签发（`charter/spiffe.py`，SVID + URI SAN + 信任域）

**v2.4 已实现 / v2.4 Shipped:**
- ✅ 多模型 judge 共识评分（`charter/judge_consensus.py`，均值/中位数 + 一致性矩阵 + 置信度，离线 fallback）
- ✅ 跨会话记忆 LLM 摘要压缩（`charter/memory_compress.py`，episode → 关键事实 + 一句话摘要，LLM/heuristic 可插拔）
- ✅ Trace SLO 接真实告警（`charter/slo_alerts.py`，Alertmanager / PagerDuty，retry-safe payload）
- ✅ SPIFFE 接真实 SPIRE Server（`charter/spiffe_grpc.py`，gRPC 通道 + 本地 fallback，调用形态一致）
- ✅ 模板 PR 自动 CI + 社区评分（`charter/pr_community.py`，spec-integrity gate + helpful/adopted/reported 加权分）

**v2.5 已实现 / v2.5 Shipped:**
- ✅ 多 provider judge 加权投票（`charter/judge_voting.py`，按历史准确率调权 + 一致性）
- ✅ 记忆分层压缩（`charter/memory_hierarchy.py`，episode → session → project 三级）
- ✅ Prometheus Alertmanager 规则自动生成（`charter/prometheus_rules.py`，SLO-aware PromQL + Alertmanager provisioning）
- ✅ SPIRE gRPC 工作负载 attestation（`charter/spiffe_attestation.py`，k8s_pod/jwt/opaque 三类 + 本地 fallback）
- ✅ 真实 GitHub PR 评论评分 + auto-merge gate（`charter/pr_comment_scoring.py`）
- ✅ 跨仓库多 agent checkpoint 共享（`charter/cross_repo.py`，file-backed 总线 + 回灌 core）

**v2.6 候选 / v2.6 Candidates:**
- 加权投票接真实 LLM-as-judge 多 provider 并发 + 结果缓存
- 记忆分层压缩接向量聚类（同类 episode 自动归并）
- Prometheus 规则接 Grafana Mimir 多租户 + 自动 label propagation
- SPIRE attestation 接 k8s SPIRE Agent（workload API）真实 mTLS
- PR 评论评分接语义分析（LLM 解析评论情感/具体性）
- 跨仓库 checkpoint 接团队级共享存储（S3 / GCS）+ 审计日志



- **可观测性升级**：`trace_operation` 输出标准 OpenTelemetry，接入 Grafana / Jaeger
- **加密身份 / Cryptographic Identity**：每个 Agent 签发 X.509 证书，工具调用 mTLS 签名，防重放
- **自进化治理 / Self-Evolving Governance**：基于 `query_trace` 历史自动建议规则调整
- **向量记忆 / Vector Memory**：`charter/memory.py` 升级为向量检索后端（当前为 SQLite 关键词召回）
- **多仓库协作 / Multi-repo**：跨 repo 的 checkpoint 共享与团队级审计
- **SOP 模板市场 / Template Marketplace**：社区发布行业 SOP（金融 / 医疗 / 电商）
- **生产评估闭环 / Continuous Eval**：`evaluate_agent` 接入 LLM 打分器，输出回归检测
## 十二、术语表 / Glossary

| 术语 | 定义 |
|------|------|
| Checkpoint | 系统在特定时间点的全量状态快照，支持恢复到该点 |
| Runtime | AI模型的运行时环境（如 claude-code、codex、copilot） |
| Guardrails | 运行时安全护栏，对输入/输出进行双向校验 |
| Worktree | Git 的独立工作区，基于同一仓库的不同分支 |
| TDD | Test-Driven Development，测试驱动开发 |
| Red-Green-Refactor | TDD 三步骤：写失败测试(Red)→写通过代码(Green)→重构(Refactor) |
| Trace/Span | 分布式追踪的基本单元，Trace是完整请求链路，Span是链路中的子操作 |
| Autonomous Mode | 一次审批后自动推进多个阶段的执行模式 |
| Fan-out/Fan-in | 并行编排模式，先分散执行多个子任务再汇总结果 |
| SBOM | Software Bill of Materials，软件物料清单 |
| Drop-box | 版本化的异步知识共享机制，团队追加约定到共享Markdown文件 |
| Model Registry | 模型运行时注册表，支持动态发现、健康检查、能力标签 |
| PREFERENCES.md | 项目级偏好配置文件，定义模型分配策略和降级规则 |

---

## 十三、风险评估 / Risk Assessment

| 风险项 | 影响 | 概率 | 缓解措施 |
|--------|------|------|----------|
| Checkpoint 状态膨胀 | 存储成本增加 | 中 | 设置保留策略和自动清理 |
| 多模型调度延迟 | 任务执行变慢 | 低 | 模型注册表缓存 + 健康检查预检 |
| TDD 纪律过严导致开发效率下降 | 开发体验下降 | 中 | 可配置严格级别，允许白名单豁免 |
| Guardrails 误拦截 | 正常操作被阻断 | 低 | 白名单机制 + 误拦截反馈学习 |
| 自动驾驶模式风险 | 自动操作产生意外结果 | 低 | 高风险操作始终人工确认 + 完整审计 |
| 早期预览版兼容 | 旧格式状态文件被 v1.0 误读 | 低 | 升级前备份 + 格式向后兼容 |

---

## 附录 / Appendix: Competitor References

本 Skill 定义基于以下竞品项目的深度分析：

1. LangGraph - https://github.com/langchain-ai/langgraph
2. CrewAI - https://github.com/crewai-inc/crewai
3. AG2 (原AutoGen) - https://github.com/ag2ai/ag2
4. OpenAI Agents SDK - https://github.com/openai/openai-agents-sdk
5. GitHub Squad - https://github.com/bradygaster/squad
6. GitHub Agentic Workflows - https://docs.github.com/actions
7. autonomous-dev-team - https://github.com/zxkane/autonomous-dev-team
8. agent-skills - https://github.com/addyosmani/agent-skills
9. Orchestrator (backnotprop) - https://github.com/backnotprop/orchestrator
10. Superpowers - https://github.com/obra/superpowers

**v2.6 已实现 / v2.6 Shipped:**
- ✅ 多 provider 投票并发 + 结果缓存（`charter/judge_concurrency.py`，ThreadPoolExecutor + LRU/SQLite 缓存）
- ✅ 记忆向量聚类（`charter/memory_clustering.py`，阈值式层次聚类，episode → K 个 cluster 摘要）
- ✅ Mimir 多租户 + label 传播（`charter/mimir_multitenant.py`，tenant-scoped SLO 规则 + Grafana 数据源 provisioning）
- ✅ 真实 k8s SPIRE Agent mTLS（`charter/spire_k8s_mtls.py`，agent config JSON + k8s values + SPIFFE env）
- ✅ PR 评论 LLM 情感/具体性分析（`charter/pr_sentiment.py`，可插拔 LLM/heuristic，逐条 + 聚合）
- ✅ 跨仓库 checkpoint 接团队共享存储 + 审计日志（`charter/checkpoint_shared.py`，S3/GCS/文件系统 + JSONL 审计）

**v2.7 候选 / v2.7 Candidates:**
- 并发投票接分布式 judge 池（K8s Job 多副本）
- 记忆聚类接 LLM 聚类标签 + 自动命名
- Mimir 接 Grafana OnCall（alert routing）
- k8s SPIRE 接真实 node agent 的 SPIFFE socket 握手
- PR 评论接 LLM 自动补全/改写建议
- checkpoint 共享接 S3 版本化 + 跨 region 复制 + 团队级 RBAC

**v2.7 已实现 / v2.7 Shipped:**
- ✅ 分布式 judge 池（`charter/judge_pool.py`，K8s Job 多副本 + 按 provider 聚合 + 无集群 plan-only）
- ✅ 记忆 LLM 自动命名聚类（`charter/cluster_naming.py`，1-3 词名 + 一行描述，可插拔 LLM/heuristic）
- ✅ Mimir → Grafana OnCall 告警路由（`charter/oncall_routing.py`，tenant/severity → 团队 integration + 升级窗口）
- ✅ 真实 k8s SPIRE node-agent socket 握手（`charter/spire_node_handshake.py`，k8s 清单 + 校验 + 握手步骤计划）
- ✅ PR 评论 LLM 自动补全/改写建议（`charter/pr_autosuggest.py`，rewrites/followups/action_items，可插拔 LLM/heuristic）
- ✅ S3 版本化 + 跨 region 复制 + 团队 RBAC（`charter/checkpoint_rbac.py`，owner/admin/member/viewer 门 + 版本化/CRR JSON）

**v2.8 已实现 / v2.8 Shipped:**
- ✅ 分布式 judge 池接真实 K8s 集群 + 结果落 S3 + 自动扩缩（`charter/judge_pool_live.py`，create/wait_and_collect/store_to_s3 + KEDA/HPA）
- ✅ 记忆多语言自动命名（`charter/cluster_multilingual.py`，detect_language + multilingual_name_clusters，可插拔 LLM/heuristic）
- ✅ OnCall 接 Grafana gRPC API 真实投递（`charter/oncall_deliver.py`，OnCallClient.deliver + route_and_deliver，离线安全 payload-only）
- ✅ 真实 k8s SPIRE node-agent 双向 mTLS（`charter/spire_bidir_mtls.py`，client+server SVID + mutual verify-peer + k8s values + 握手计划）
- ✅ PR 评论 LLM diff 级代码补全（`charter/pr_diff_completion.py`，hunks + comments → before/after 改写 + rationale，可插拔 LLM/heuristic）
- ✅ checkpoint RBAC 生成真实 IAM/S3 bucket policy（`charter/checkpoint_iam.py`，per-role IAM + deny-default bucket policy + bundle）

**v2.9 候选 / v2.9 Candidates:**
- 分布式 judge 池接 K8s 集群自动扩缩（KEDA 多触发源 + 成本感知）
- 记忆多语言命名接跨语言 episode 自动归并（同主题不同语言合并）
- OnCall 接真实 Grafana gRPC channel 投递（非 plan-only）
- k8s SPIRE 双向 mTLS 接真实 node agent socket 回归测试
- PR diff 补全接多文件 + 跨 hunk 一致性校验
- checkpoint IAM 接真实 AWS 账号生成 + 策略自动 apply + 审计


