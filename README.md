# Charter Orchestrator

> **Full-Lifecycle Governance & Orchestration Framework for AI Agents**
>
> Defines how Agents work, to what standard, and when to stop for human confirmation
>
> 定义 Agent 怎么干活、干到什么标准、什么时候该停下来让人确认

[![Version](https://img.shields.io/badge/version-3.11.0-blue.svg)](https://github.com/JarvisCao168/charter-orchestrator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Skill Definition](https://img.shields.io/badge/Skill-v2.1.0-green.svg)](SKILL.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Agent--Independent-brightgreen.svg)](.)

---


## ⚡ 可执行 / Runnable (v1.1)

v1.1 把治理规范变成了可运行的 Python 包。5 分钟跑通：

```bash
git clone https://github.com/JarvisCao168/charter-orchestrator.git
cd charter-orchestrator
pip install -e .
python -m charter.cli demo     # 10 阶段 + 门禁 + TDD + Guardrails + 评估全跑通
```

- **executable core**: `charter/` (core, governance, observability, evaluation, memory)
- **10 automated tests**: `python -m pytest tests/`
- **quick start**: [`docs/quickstart.md`](docs/quickstart.md)
- **fault-coverage proof**: [`docs/fault_coverage.md`](docs/fault_coverage.md)

## 🔄 MCP Server (v3.1)

Charter now ships a stdio MCP server — mount the governance framework directly
into Claude Code, Codex, or any MCP client:

```bash
pip install -e ".[mcp]"          # or: pip install charter-orchestrator[mcp]
python -m charter.mcp_server     # stdio JSON-RPC
```

**MCP config** (Claude Desktop / Codex / `.mcp.json`):

```json
{
  "mcpServers": {
    "charter-orchestrator": {
      "command": "python",
      "args": ["-m", "charter.mcp_server"]
    }
  }
}
```

- **20 tools** exposed: `init_project`, `advance_stage`, `confirm_gate`,
  `query_status`, `query_rule`, `list_skills`, `execute_in_sandbox`,
  `create_dropbox`, `manage_task_lifecycle`, `trigger_workflow`,
  `create_chat_chain`, `save_checkpoint`, `restore_checkpoint`,
  `dispatch_to_model`, `manage_worktree`, `enforce_tdd`, `guardrails`,
  `enable_autonomous_mode`, `trace_operation`, `query_trace`
- **47 skills** as MCP resources (`charter://skills/<id>`), each with I/O contract
- **SKILL.md** upgraded to Anthropic-compatible YAML frontmatter (native Claude Code discovery)


## 📦 v3.2 — 107 Skills + MCP SSE/HTTP

- **Skills: 47 → 107** — 60 new structured skills mapped to the 58 charter modules
  (dev +8, security +8, obs +10, collab +8, analysis +6, test +6, deploy +8, tool +6).
  Each carries a `module` ref to the exact Python module that operationalizes it.
- **MCP SSE/HTTP transport** — optional stdlib-only HTTP+SSE server alongside the default
  stdio transport:
  ```bash
  python -c "from charter.mcp_server import run_http_server; run_http_server('0.0.0.0', 8765)"
  # GET /mcp/health · GET /mcp/tools · GET /mcp/sse · POST /mcp/message?client=<cid>
  ```
- `scripts/validate_skills.py` enforces the 107-skill invariant in CI.
- 292 tests, all green on 3.9 / 3.11 / 3.12.


## 🔬 v3.3 — Per-Skill 单元测试 + demo-skill 一键跑通

- **60 个新 skill 逐个补单元测试**：`tests/test_v3_3_skills.py`，每个 skill 真正调用
  对应 charter 模块的公开入口（不是只校验路径/类别）。55 个独立模块，覆盖
  SLO→OnCall、Judge Pool、Memory 压缩/聚类/向量合并、mTLS/SPIFFE/SPIRE、
  PR diff 语义、IAM/RBAC 等全部 60 个 v3.2 新增 skill。
- **`make demo-skill SKILL=<id>` 一键跑通真实模块链路**：
  `charter/demo_skill.py` + `Makefile`。对 28 个 skill 提供端到端 demo runner
  （SLO→OnCall / Judge Pool K8s / Memory 全链路 / mTLS+SPIFFE / PR diff / IAM+RBAC），
  其余 79 个走 generic import+introspection 回退。
  ```bash
  make demo-skill SKILL=obs_09          # SLO breach -> alert -> OnCall gRPC e2e
  make demo-skill SKILL=dep_06 JSON=1   # 机器可读
  make list-skill                        # 列出有 bespoke demo 的 28 个 skill
  ```
- 334 测试（原 260 + 60 skill + 9 demo-skill + 调整），3.9 / 3.11 / 3.12 全绿。


## 🔐 v3.4 — demo-skill --all + MCP X-API-Key 鉴权

- **`make demo-skill SKILL=... --all`**：`run_all_demos()` 一次跑全部 6 类 bespoke 链路
  （SLO→OnCall / Judge Pool / Memory / mTLS+SPIFFE / PR diff / IAM+RBAC），失败不中断，
  返回 `total/passed/failed/chains/per_skill` 汇总；`--json` 出机器可读报告。
- **MCP SSE/HTTP X-API-Key 鉴权**：`HTTPMCPServer` / `run_http_server` 支持
  `api_key=` 参数或 `CHARTER_MCP_API_KEY` 环境变量，网关所有 `/mcp/*` 端点；
  未配置时保持开放（向后兼容）。常数时间比较防时序泄露。
- 348 测试（原 334 + 7 demo +4 auth +3 版本调整），3.9 / 3.11 / 3.12 全绿。


## 📈 v3.5 — demo-skill --watch SLO 告警 + MCP /metrics

- **`make demo-skill SKILL=--watch`**：`run_watch()` 持续跑 6 类 bespoke 链路，
  按可用性 SLO（`--slo-pct`，默认 90%）评估通过率，低于阈值产生结构化告警
  （severity + failed_skills + message）；`--iterations` 控制轮数，`--json` 出机器可读。
- **MCP `/metrics` 端点**：Prometheus 文本格式，暴露 `charter_mcp_requests_total`
  （method/endpoint/status 标签）、`charter_mcp_requests_by_endpoint_total`、
  `charter_mcp_uptime_seconds`。线程安全计数；`/metrics` 无需 X-API-Key（scrapers 匿名可抓），
  其余端点维持鉴权。
- 352 测试（原 341 + 7 watch +4 metrics +3 版本调整），3.9 / 3.11 / 3.12 全绿。


## 🔔 v3.6 — MCP 资源订阅 + SSE metrics 实时流 + watch 接 OnCall gRPC

- **MCP resources 订阅**：`resources/subscribe` / `resources/unsubscribe` /
  `resources/list_subscriptions`（按 client 隔离，线程安全）；新增 `charter://metrics`
  资源（Prometheus 快照，HTTP 模式回读实时计数器，stdio 模式静态说明）。
- **SSE metrics 实时流**：`/mcp/sse?stream=metrics` 每 5s 推一帧
  `charter_mcp_requests_total` / `by_endpoint_total` / `uptime_seconds`，多行
  data 按 SSE 规范拆分，供仪表盘实时刷新。
- **demo-skill watch 接 OnCall**：`run_watch(oncall_target=...)` 把 SLO 告警通过
  `oncall_grpc_e2e` 真正投递到 Grafana OnCall（gRPC）；无 `grpc` 时降级 plan-only
  receipt，CI 仍绿。CLI：`make demo-skill SKILL=--watch --oncall-target ...`。
- 361 测试（原 352 + 5 + 4 + 1），3.9 / 3.11 / 3.12 全绿。


## ⚡ v3.7 — MCP resources/changed 主动通知 + watch 接 Alertmanager webhook

- **MCP 资源变更推送**：`notify_resource_changed()` + `_broadcast_metrics_change()`，
  订阅 `charter://metrics` 的 SSE client 在每次请求计数变化时收到
  `notifications/resources/updated` 事件（含最新 Prometheus 快照）。
- **SSE metrics 事件驱动**：`/mcp/sse?stream=metrics` 先推初始快照，之后阻塞等
  push 事件（30s keepalive），替代 v3.6 的 5s 轮询循环。
- **demo-skill watch 接 Alertmanager**：`run_watch(alertmanager_url=...)` 把 SLO 告警
  以 Alertmanager v4 JSON 格式 POST 到 webhook（`_post` seam 可注入测试桩 / 认证传输），
  网络失败降级 plan-only，CI 仍绿。CLI：`--alertmanager-url ... --alertmanager-timeout N`。
- 372 测试（原 361 + 6 MCP 事件通知 + 5 Alertmanager + 1 版本净增），3.9 / 3.11 / 3.12 全绿。


## 🔌 v3.8 — MCP 工具结果自动推送 + demo-skill watch --promql 模式

- **MCP 工具结果订阅**：`tools/subscribe_result` / `tools/unsubscribe_result` /
  `tools/list_result_subscriptions`（按 tool 名订阅结果变化）；`tools/call` 执行后
  自动向订阅 client 推 `notifications/resources/updated`（resource
  `charter://tools/<name>/result`，payload 含完整结果）。
- **demo-skill watch `--promql` 模式**：`run_watch_from_promql(base_url, promql,
  threshold_fn, iterations, ...)` 每轮向 Prometheus 发一条 PromQL 查询，
  由 `threshold_fn` 评估；不达标时通过 OnCall + Alertmanager 双通道投递告警。
  CLI：`python -m charter.demo_skill --promql 'error_rate:rate5m' \
       --prometheus-base http://localhost:9090 --prometheus-threshold 0.01`。
- 388 测试（原 372 + 4 工具结果推送 + 7 --promql + 1 版本净增），3.9 / 3.11 / 3.12 全绿。


## 📊 v3.9 — MCP 工具结果 read 侧 + demo-skill watch --promql 区间聚合模式

- **MCP 工具结果 read 侧**：`charter://tools/<name>/result` 现可用
  `resources/read` 读取（调用过 → JSON 结果，未调用 → found=false 说明）；
  每次 `tools/call` 自动记录最新结果（`_tool_results` 线程安全存储），
  补齐 v3.8 只有 push 侧的工具结果 resource。
- **demo-skill watch `--promql` 区间聚合**：`run_watch_from_promql(range_mode=True)`
  查 `query_range`（`--prometheus-range-window` + `--prometheus-range-step`），
  用 `_aggregate_range_values`（`--prometheus-range-agg` avg/max/min/sum/p95）
  聚合成单点判 SLO，替代单点 instant query；报告标记 `promql-range` 模式。
  ```bash
  python -m charter.demo_skill --promql 'error_rate' --prometheus-base http://localhost:9090 \
      --prometheus-range --prometheus-range-window 5m --prometheus-range-agg p95 \
      --prometheus-threshold 0.01 --json
  ```
- 394 测试（原 383 + 3 工具结果 read + 8 range 聚合 + 1 版本净增 + 2 调整），3.9 / 3.11 / 3.12 全绿。


## 🧠 v3.10 — MCP 推送携带 last_result 全文 + demo-skill watch --snapshot 持久化

- **MCP 推送携带全文**：`_tool_result_payload(tool_name)` 构建与 `resources/read`
  同构的 JSON 载荷；`tools/call` 触发的 `resources/changed` 事件现带 `last_result`
  字段（完整结果），订阅者免再发 `resources/read` —— 呼应多 Agent 一致性分析
  中"事件溯源：状态由事件流派生、可追溯、解耦"的轻量落地。
- **demo-skill watch `--snapshot`**：`_snapshot_watch_report(report, path, ...)`
  把本轮 watch 报告（SLO 历史 / 告警 / OnCall+Alertmanager 投递 receipt /
  Prometheus 查询）落盘 JSON 快照，自动建父目录，写失败不丢报告；契合
  "时间旅行调试 / 重放事件流复现 Bug"。CLI：`--snapshot PATH`（对 `--watch` 与
  `--promql` 都生效）。
  ```bash
  python -m charter.demo_skill --watch --iterations 3 --slo-pct 90 \
      --snapshot ./audit/watch-$(date +%s).json
  ```
- 402 测试（原 394 + 3 推送全文 + 5 --snapshot + 1 版本净增 + 3 调整），3.9 / 3.11 / 3.12 全绿。

## 🛡️ v3.11 — 四大治理模块（事件溯源 / 反思 / 语义追踪 / 成本路由）

基于《多Agent系统数据一致性与高可靠协同架构设计分析报告》进阶设计落地：

- **`validation_gateway.py`**：三层校验网关（schema 契约 / 数据对齐 / 一致性矛盾）
  + 熔断器（closed→open→half-open），`check_with_retry` 本地重试后降级不崩链路。
- **`critic_agent.py`**：全局反思器——`pre_check`（结构审查：悬挂依赖/环/重复产出）、
  `post_audit`（逻辑审查 + 可插拔规则）、`repair`（生成修复补丁，"报错"变"自愈"）。
- **`semantic_trace.py`**：全链路语义追踪——`SemanticTracer` 记录每次工具调用
  的输入→输出 embedding 余弦相似度，偏差 < 阈值自动判幻觉并拦截（`make_embedder`
  有 key 走 LLM、无 key 离线 fallback，CI 仍绿）。
- **`model_router.py`**：小模型路由 + 语义缓存——`TaskProfile.complexity()` 打分，
  `ModelRouter` 选最便宜合格 tier，`SemanticCache` LRU 降 token 成本。

四条全链路 demo：`make demo-skill SKILL=gov_01`（`gov_01..gov_04`），
一条命令跑通 反思 → 网关 → 熔断 → 语义追踪 → 模型路由 → 缓存 全链路。

455 测试（原 402 + 53），3.9 / 3.11 / 3.12 全绿。

## 目录 / Table of Contents

- [概述 / Overview](#概述-overview)
- [核心能力 / Core Capabilities](#核心能力-core-capabilities)
- [架构总览 / Architecture](#架构总览-architecture-overview)
- [快速开始 / Quick Start](#快速开始-quick-start)
- [工具一览 / Tools](#工具一览-tool-reference)
- [Skills 工具箱 / Skills](#skills-工具箱-skills-toolbox)
- [治理规则体系 / Governance](#治理规则体系-governance-rules)
- [6 道防线 / 6 Defense Lines](#6-道防线-6-defense-lines)
- [自动驾驶模式 / Autonomous Mode](#自动驾驶模式-autonomous-mode)
- [外部集成 / Integrations](#外部集成-external-integrations)
- [版本路线图 / Roadmap](#版本路线图-version-roadmap)
- [商业化 / Commercialization](#商业化-commercialization)
- [贡献指南 / Contributing](#贡献指南-contributing-guide)
- [许可证 / License](#许可证-license)

---

## 概述 / Overview

Charter Orchestrator 是一个 **"治理 + 流程 + 工具"** 三位一体的智能体编排框架。它在整合 GitHub Squad、ChatDev、GitHub Agentic Workflows、OpenHands 等项目核心优势的基础上，经过对 LangGraph、CrewAI、AG2、OpenAI Agents SDK、autonomous-dev-team、agent-skills、Superpowers、Orchestrator 等 10+ 个同类项目的深度竞品分析，实现了从"流程编排框架"到"企业级智能体治理平台"的全面跃迁。

### 一句话定位 / One-line Positioning

> GitHub 上现有的 Agent 项目解决的是 **"怎么让 Agent 做事"**（引擎/工具/执行），而 Charter Orchestrator 解决的是 **"怎么管理 Agent 做事"**（治理/流程/规则）—— 它是 **Agent 之上的管理层**，而非 Agent 本身。

### 类比理解 / Analogy

| 类比 | 说明 |
|------|------|
| 容器 vs Kubernetes | Agent frameworks (LangGraph/CrewAI) are containers; Charter Orchestrator is K8s |
| 工具 vs 宪法 | Agent is the tool; governance rules are the constitution |
| 引擎 vs 自动驾驶系统 | Agent is the engine; Charter Orchestrator is the autopilot ensuring safe driving |

---

## 核心能力 / Core Capabilities

| 能力 | 说明 |
|------|------|
| **10-Stage Full-Lifecycle SOP** / **10 阶段全链路 SOP** | 从阶段〇（基础条件调查）到阶段九（复盘沉淀），覆盖完整软件开发生命周期 |
| **20 Orchestration Tools** / **20 个编排工具** | 基础工具 6 个 + 新增工具 9 个 + 增强工具 6 个 |
| **47 Skills** / **47 个 Skills** | 9 大分类：环境/分析/开发/测试/交付/协作/工具/安全/可观测性 |
| **13 Governance Rule Categories** / **13 类治理规则** | 角色分工、权限边界、沟通规范、安全红线、代码质量、Token 预算、Checkpoint、多模型调度、TDD、Guardrails、自动驾驶、事件驱动、规则查询 |
| **6 Defense Lines** / **6 道防线** | 需求澄清 → 文档固化 → 人类审批 → 分支隔离 → TDD 红绿 → 发版自检 |
| **Hard Gate Mechanism** / **硬门禁机制** | `confirm_gate` 物理阻断，未通过门禁的 Agent 无法越级推进 |
| **Checkpoint Snapshot & Restore** / **Checkpoint 快照恢复** | 任意节点状态快照，支持回滚与分支 |
| **Multi-Model Dispatch** / **多模型调度** | 支持 6+ 种 Runtime 实时发现、智能分配与自动降级 |
| **Guardrails Security** / **Guardrails 安全护栏** | 输入/输出双向校验，防止越权操作和数据泄露 |
| **TDD Enforcement** / **TDD 强制纪律** | 红-绿-重构循环强制执行，未通过时代码提交门禁自动阻断 |
| **Git Worktree Isolation** / **Git Worktree 隔离** | 多任务并行开发零冲突 |
| **Autonomous Mode** / **自动驾驶模式** | 一次审批后自主运行多个阶段，关键验证点保留自动检查 |
| **Observability** / **可观测性** | Trace/Span 全链路追踪，操作审计与指标暴露 |

---

## 架构总览 / Architecture Overview

```
+------------------------------------------------------------------+
|                    Charter Orchestrator v1.0                     |
+------------------------------------------------------------------+
|  [可观测性层]  Trace/Span 全链路追踪 · 审计增强 · 指标暴露        |  <- v1.0 新增
+------------------------------------------------------------------+
|  [Guardrails层]  输入校验 · 输出过滤 · 安全护栏 · 合规审计        |  <- v1.0 新增
+------------------------------------------------------------------+
|  [Checkpoint层]  快照 · 回滚 · 分支 · 恢复                       |  <- v1.0 新增
+------------------------------------------------------------------+
|  [治理总纲]      角色分工 · 权限边界 · 沟通规范 · 安全红线        |
|                  · 代码质量 · Token预算 · 治理规则查询             |
+------------------------------------------------------------------+
|  [执行流程]      10阶段SOP · 门禁机制 · 阶段-Skill映射            |
|                  · 事件驱动 · 任务链 · 自动驾驶模式                |  <- v1.0 增强
+------------------------------------------------------------------+
|  [工具层]        11基础工具 + 9新增工具 + 6增强工具                |
|                  + CheckpointManager + ModelDispatcher            |  <- v1.0 新增
|                  + GuardrailsEngine + TDDEnforcer                 |  <- v1.0 新增
|                  + WorktreeManager + ObservabilityLayer           |  <- v1.0 新增
+------------------------------------------------------------------+
|  [制度层]        9类治理规则 + 4类新增规则                        |
|                  + Checkpoint规则 + Guardrails规则                |  <- v1.0 新增
|                  + TDD规则 + AutonomousMode规则                   |  <- v1.0 新增
+------------------------------------------------------------------+
```

---

## 快速开始 / Quick Start

### 前置条件 / Prerequisites

- 智能体平台支持 Skill 机制（如 Hermes）
- 将 `SKILL.md` 部署到平台的 Skills 目录

### 第一步 / Step 1: Initialize Project

Send the following instruction to the agent:

对智能体发出以下指令：

```
请调用 init_project 工具，初始化以下项目：
- 项目名称：电商智能客服自动化
- 项目类型：software_dev
- 核心目标：搭建基于大模型的智能客服系统，支持多轮对话、工单自动分类、知识库检索增强
```

### 第二步 / Step 2: Advance Stage

After initialization, advance stage by stage:

项目初始化完成后，按阶段逐步推进：

```
请调用 advance_stage 工具，推进到阶段一（需求分析）。
```

### 第三步 / Step 3: Query Status

Check project progress at any time:

随时了解项目进度：

```
请调用 query_status 工具，展示当前项目全貌。
```

### 第四步 / Step 4: Query Rules

When in doubt about compliance:

遇到合规疑问时：

```
请调用 query_rule 工具，查询"安全红线"相关条款。
```

### 进阶 / Advanced: Enable Autonomous Mode (v1.0)

For medium-to-low-risk projects, enable autonomous mode — one approval runs multiple stages:

对于中低风险项目，可启用自动驾驶模式，一次审批后自主运行：

```
请调用 enable_autonomous_mode 工具：
- 项目ID：your-project-id
- 起始阶段：stage_5
- 结束阶段：stage_7
- 审批级别：standard
```

---

## 工具一览 / Tool Reference

### 基础工具 / Base Tools (v1.0)

| 工具 / Tool | 描述 / Description | 适用阶段 / Stages |
|------|------|----------|
| `init_project` | 初始化项目，创建工作区、配置环境、注册模型、注入 Guardrails | 阶段〇 |
| `advance_stage` | 推进项目到下一阶段，执行前置检查和门禁 | 全阶段 |
| `confirm_gate` | 执行门禁确认，检查产出物质量、安全校验、审计日志 | 全阶段门禁点 |
| `query_status` | 查询项目当前状态全貌（含可观测性指标） | 全阶段 |
| `query_rule` | 运行时即时查询章程条款（"边干活边翻法条"） | 全阶段 |
| `list_skills` | 列出当前项目可用的所有 Skills，支持筛选 | 全阶段 |

### v1.0 增强工具 / Enhanced Tools

| 工具 / Tool | 描述 / Description | 灵感来源 / Inspired By |
|------|------|----------|
| `execute_in_sandbox` | 沙箱化代码执行（隔离环境 + 多模型调度 + Guardrails 过滤） | OpenHands |
| `create_dropbox` | 异步知识共享机制（版本化 Markdown 文档协作） | GitHub Squad |
| `manage_task_lifecycle` | 任务生命周期管理（创建/分配/执行/完成/归档） | LobeHub |
| `trigger_workflow` | 事件驱动工作流引擎（Issue/PR/定时/Webhook 触发） | GitHub Agentic Workflows |
| `create_chat_chain` | 原子任务链生成（顺序/并行/条件分支） | ChatDev |

### v1.0 新增工具 / New Tools (v1.0)

| 工具 / Tool | 描述 / Description | 灵感来源 / Inspired By |
|------|------|----------|
| `save_checkpoint` | 任意节点状态快照保存 | LangGraph |
| `restore_checkpoint` | 恢复到指定快照状态 | LangGraph |
| `dispatch_to_model` | 智能模型调度与降级（6+ Runtime 实时发现） | Orchestrator |
| `manage_worktree` | Git Worktree 多环境隔离 | autonomous-dev-team |
| `enforce_tdd` | TDD 红绿循环强制纪律 | Superpowers |
| `guardrails` | 输入/输出安全护栏 | OpenAI Agents SDK |
| `enable_autonomous_mode` | 一次审批自动驾驶模式 | agent-skills |
| `trace_operation` | 操作追踪与 Span 记录 | LangSmith |
| `query_trace` | 追踪记录查询与分析 | LangSmith |

---

## Skills 工具箱 / Skills Toolbox

v1.0 共 **47 个 Skills**，分为 9 大分类：

### 环境与基础设施（7 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| env_01 | EnvironmentProbe | 自动 | 〇 | 基础环境探测与能力发现 |
| env_02 | SandboxProvisioner | 自动 | 〇 | 沙箱环境快速搭建 |
| env_03 | ModelRegistryProbe | 自动 | 〇 | 发现可用模型 Runtime |
| env_04 | GuardrailsBaseline | 自动 | 〇 | 配置项目级安全护栏基线 |
| env_05 | WorktreeProvisioner | 自动 | 五 | 创建隔离开发环境 |
| env_06 | TDDSetup | 自动 | 五 | 配置 TDD 测试框架 |
| env_07 | DependencyManager | 自动 | 五 | 依赖管理与版本锁定 |

### 分析与决策（6 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| analysis_01 | CompetitorAnalyzer | 自动 | 一 | 竞品功能/架构/生态分析 |
| analysis_02 | FeasibilityAssessor | 自动 | 一 | 技术/经济/时间可行性评估 |
| analysis_03 | RiskAssessor | 自动 | 一 | 技术风险/安全风险/合规风险评估 |
| analysis_04 | DistillationDecider | 自动 | 三 | 开源蒸馏决策（含合规+复杂度+兼容性） |
| analysis_05 | ArchitectureReviewer | 自动 | 四 | 架构决策自动评审 |
| analysis_06 | CostOptimizer | 自动 | 三 | 模型成本评估与优化建议 |

### 开发与工程（12 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| dev_01 | CodeGenerator | 自动 | 六 | 基于需求和设计生成代码 |
| dev_02 | APIDesignPro | 自动 | 六 | RESTful/GraphQL API 设计审查与优化 |
| dev_03 | FrontendEngineer | 自动 | 六 | 现代前端架构、组件设计、性能优化 |
| dev_04 | DatabaseArchitect | 自动 | 六 | schema 优化、索引策略、查询性能 |
| dev_05 | CodeReviewer | 自动 | 六 | 代码质量审查与改进建议 |
| dev_06 | SecurityAuditor | 自动 | 六 | 代码安全扫描、依赖漏洞检测、合规检查 |
| dev_07 | PerformanceEngineer | 自动 | 六 | 性能基线建立与优化建议 |
| dev_08 | TDDEnforcer | 每次提交 | 六 | 强制红绿循环（Red→Green→Refactor） |
| dev_09 | TechDebtTracker | 自动 | 六 | 技术债务识别与追踪 |
| dev_10 | RefactoringAssistant | 自动 | 六 | 代码重构辅助与风险评估 |
| dev_11 | SBOMGenerator | 自动 | 八 | 软件物料清单生成 |
| dev_12 | BuildPipeline | 自动 | 八 | 构建流水线配置与执行 |

### 测试与验证（5 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| test_01 | TestPlanner | 自动 | 七 | 测试计划制定与用例设计 |
| test_02 | TestExecutor | 自动 | 七 | 自动化测试执行与结果分析 |
| test_03 | PerformanceBaseline | 自动 | 七 | 性能基准测试与对比分析 |
| test_04 | SecurityTest | 自动 | 七 | 安全测试（渗透/漏洞/合规） |
| test_05 | AcceptanceValidator | 自动 | 七 | 验收标准验证与确认 |

### 交付与运维（4 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| deploy_01 | ReleaseManager | 自动 | 八 | 版本封装与发布管理 |
| deploy_02 | SecurityAuditFinal | 自动 | 八 | 发布前最终安全审计 |
| deploy_03 | DeploymentOrchestrator | 自动 | 八 | 多环境部署编排 |
| deploy_04 | RollbackManager | 自动 | 八 | 回滚策略制定与执行 |

### 协作与记忆（4 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| collab_01 | DropBoxManager | 自动 | 全阶段 | 异步知识共享与版本化文档协作 |
| collab_02 | TaskChainOrchestrator | 自动 | 全阶段 | 原子任务链生成与执行编排 |
| collab_03 | MeetingRecorder | 自动 | 全阶段 | 会议纪要与决策记录 |
| collab_04 | KnowledgeGraph | 自动 | 九 | 项目知识图谱构建与更新 |

### 工具与版本控制（4 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| tool_01 | GitWorkflow | 自动 | 全阶段 | Git 工作流管理与分支策略 |
| tool_02 | CI_CDPipeline | 自动 | 六~八 | CI/CD 流水线配置与执行 |
| tool_03 | VersionManager | 自动 | 全阶段 | 语义化版本管理与变更追踪 |
| tool_04 | ConfigManager | 自动 | 〇 | 项目配置管理与环境切换 |

### 安全与治理（3 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| security_01 | GuardrailsEngine | 自动 | 全阶段 | 运行时安全护栏执行 |
| security_02 | AuditLogger | 自动 | 全阶段 | 操作审计日志记录与管理 |
| security_03 | ComplianceChecker | 自动 | 八 | 合规检查与报告生成 |

### 可观测性（2 个）

| ID | 名称 | 触发方式 | 适用阶段 | 描述 |
|----|------|----------|----------|------|
| obs_01 | TraceCollector | 自动 | 全阶段 | Trace/Span 数据收集与聚合 |
| obs_02 | ObservabilityReport | 自动 | 九 | 可观测性报告生成与指标分析 |

---

## 治理规则体系 / Governance Rules

v1.0 共 **13 类治理规则**，覆盖从角色分工到安全护栏的完整治理体系：

| 规则类别 / Rule Category | 说明 / Description |
|----------|------|
| 角色分工规则 | 5 个治理角色定义（Hermes/Architect/Developer/Tester/Reviewer），v1.0 新增 Model Dispatcher |
| 权限边界规则 | 基于角色的操作权限矩阵，v1.0 新增 Guardrails 权限校验维度 |
| 沟通规范规则 | 结构化沟通模板、状态更新规范、异常上报流程 |
| 安全红线规则 | 绝对禁止项（代码注入/敏感数据泄露/未授权访问/绕过门禁），v1.0 新增自动驾驶模式安全约束 |
| 代码质量规则 | 编码规范、审查标准，v1.0 新增 TDD 红绿循环检查 |
| Token 预算规则 | 项目级/阶段级 Token 预算分配，v1.0 新增多模型分级计价 |
| 治理规则查询规则 | query_rule 工具运行时即时查询 |
| **Checkpoint 状态管理规则** | 快照策略/保留策略/恢复权限/审计要求（v1.0 新增） |
| **多模型调度规则** | 模型发现/分配策略/降级规则/成本管控/偏好配置（v1.0 新增） |
| **TDD 纪律规则** | 强制红绿循环/测试覆盖率门槛/禁止跳过/技术债务追踪（v1.0 新增） |
| **Guardrails 安全护栏规则** | 默认启用/敏感数据清单/拦截告警/白名单机制/合规报告（v1.0 新增） |
| **自动驾驶模式规则** | 启用条件/禁止场景/人工保留点/时长限制/审计要求（v1.0 新增） |
| 事件驱动规则 | 事件源/执行策略/安全约束（v1.0） |

---

## 6 道防线 / 6 Defense Lines

在门禁机制基础上，阶段六（模块化开发）新增 6 道防线：

| 防线 / Line | 检查项 / Check | 执行时机 / When | 失败处置 / On Failure |
|------|--------|----------|----------|
| 防线 1：需求澄清 | 需求是否已转化为可测试的验收标准 | 阶段二到三 | 返回阶段二补充 |
| 防线 2：文档固化 | 架构设计文档是否已签字锁定 | 阶段四门禁 | 阻断，要求补充文档 |
| 防线 3：人类审批 | 关键架构决策是否经人工确认 | 阶段五门禁 | 暂停，等待人工审批 |
| 防线 4：分支隔离 | 是否在工作区隔离环境中开发 | 阶段六入口 | 自动创建 Worktree |
| 防线 5：TDD 红绿 | 是否遵循红-绿-重构循环 | 每次代码提交 | 阻断，要求补测试 |
| 防线 6：发版自检 | 发布前全量检查清单是否通过 | 阶段八门禁 | 阻断，列出未通过项 |

---

## 自动驾驶模式 / Autonomous Mode

v1.0 新增的可选流程模式，适用于中低风险项目：

```
启动自动驾驶模式 / Launch Autonomous Mode (one human approval)
    |
    v
阶段五 / Stage 5: Dev environment setup (auto-verify)
    |
    v
阶段六 / Stage 6: Modular development (TDD enforced + auto gates)
    |   |-- 每个模块：Red -> Green -> Refactor 自动执行
    |   |-- 门禁自动检查（代码质量/安全/测试覆盖）
    |   '-- 失败时暂停并请求人工介入
    |
    v
阶段七 / Stage 7: Integration testing (auto-run + Trace analysis)
    |
    v
[High-risk checkpoint] ← Production deploy always needs human sign-off
    |
    v
阶段八 / Stage 8: Packaging & delivery (auto-pack + Guardrails check)
    |
    v
Generate autonomous-mode report (with full audit log)
```

**安全约束 / Security Constraints:**

- 仅 software_dev 和 open_source_distillation 类型项目可启用 / Only software_dev and open_source_distillation projects may use it
- internal_tool 和 research 类型禁止启用 / Forbidden for internal_tool and research projects
- 生产环境部署（阶段八）始终需要人工确认 / Production deploy (Stage 8) always requires human confirmation
- 可配置最大自动运行时长（默认 4 小时） / Configurable max auto-run time (default 4h)
- 所有自动操作完整审计记录 / All auto-operations fully audit-logged

---

## 外部集成 / External Integrations

Charter Orchestrator 可与以下主流框架和项目集成：

| 集成项目 / Project | 集成方式 / Method | 互补价值 / Value |
|----------|----------|----------|
| [LangGraph](https://github.com/langchain-ai/langgraph) | save_checkpoint/restore_checkpoint 对接 Checkpoint 持久化层 | 图状态机任意节点快照/回滚 |
| [CrewAI](https://github.com/crewai-inc/crewai) | 角色化任务分配增强 | 灵活的角色化任务分配 |
| [AG2](https://github.com/ag2ai/ag2) | 可选 ConversationMode 开关 | Agent 间自由讨论/辩论/共识 |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-sdk) | guardrails 对接 Guardrails 安全护栏 | 成熟的输入/输出双向校验 |
| [GitHub Squad](https://github.com/bradygaster/squad) | create_dropbox 对接 Drop-box 知识共享 | 仓库原生知识共享 + 独立审查 |
| [GitHub Agentic Workflows](https://docs.github.com/actions) | trigger_workflow 对接事件驱动工作流 | GitHub 原生集成 + 沙箱安全模型 |
| [autonomous-dev-team](https://github.com/zxkane/autonomous-dev-team) | manage_worktree 对接 Git Worktree 隔离 | 多任务并行开发零冲突 |
| [agent-skills](https://github.com/addyosmani/agent-skills) | Skill Registry 纳入工程领域 Skills | 补充工程技能深度 |
| [Orchestrator](https://github.com/backnotprop/orchestrator) | dispatch_to_model 对接多 Runtime 调度 | 6+ 种 AI 模型实时发现与降级 |
| [Superpowers](https://github.com/obra/superpowers) | enforce_tdd 对接 6 道防线和 TDD 纪律 | 强化开发纪律 |
| [LangSmith](https://smith.langchain.com) | trace_operation/query_trace 对接可观测性平台 | 生产级 Trace/Span 追踪 |

---

## 版本路线图 / Version Roadmap

| 版本 / Version | 状态 / Status | 核心内容 / Core Content |
|------|------|----------|
| **v2.1.0** | **当前版本（首版发布）** | 20 工具 · 47 Skills · 13 类治理规则 · 10 阶段 SOP · Checkpoint / 多模型调度 / TDD / Guardrails / 自动驾驶 / 可观测性 |
| v2.1.0 | 规划 | 社区模板市场、多仓库协作、自定义阶段模板 |
| v2.1.0 | 愿景 | 自进化治理规则、跨项目知识图谱、AI 驱动的流程优化 |

### 工具总数变化 / Tool Count Evolution

| 版本 | 基础工具 | 新增工具 | 增强工具 | 总计 |
|------|----------|----------|----------|------|
| 早期预览 | 6 | — | — | 6 |
| 中期预览 | 6 | 5 | 4 | 11 |
| **v1.0（首版发布）** | 6 | 9 | 6 | **20** |

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

---

## 商业化 / Commercialization

Charter Orchestrator 采用 **Open Core** 模式，核心引擎完全开源（MIT 协议），同时提供以下商业化服务：

| 变现模式 / Model | 说明 / Description |
|----------|------|
| 开放核心（Open Core） | 核心治理框架开源免费，企业版增加多租户管理、审计日志、SSO、合规报告、SLA 保障 |
| SaaS 云托管 | 提供 Charter Orchestrator Cloud，一键部署、免运维、按项目/按 Agent 数收费 |
| 技术支持与订阅 | 开源版免费，企业级发行版含安全补丁、7×24 支持、定制咨询 |
| 认证培训 | Charter Orchestrator 认证工程师（类似 CKA/CKAD） |
| 技能市场抽成 | Skills 上架到 SkillHub，按调用量收费或订阅制 |

### 对标参考 / Benchmark Comparison

| 项目 / Project | Stars | 商业化方式 / Model | 成果 / Outcome |
|------|-------|-----------|------|
| LangGraph | ~25K | LangSmith（SaaS）+ LangGraph Cloud（托管） | LangChain 估值约 12.5 亿美元（2025 年 10 月 IVP 领投 C 轮） |
| CrewAI | ~58K | 开源核心 + Enterprise + 托管平台 | 2024 年完成 1800 万美元融资 |
| Dify | ~148K | 开源 + 企业版 + 私有化部署 | 2026 年融 3000 万美元 Pre-A |
| GitLab | ~30K | Open Core（社区版免费 + 企业版收费） | 纳斯达克 IPO，市值最高 150 亿美元 |

---

## 贡献指南 / Contributing Guide

欢迎各种形式的贡献！

### 提交规范 / Commit Convention

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat`: 新功能
- `fix`: 修复问题
- `docs`: 文档变更
- `refactor`: 重构
- `chore`: 构建/工具变更

### 新增 Skill / Adding a Skill

1. Fork 本仓库并创建分支：`git checkout -b skill/your-skill-name`
2. 在 `SKILL.md` 的依赖 Skills 清单章节添加你的 Skill 定义
3. 确保包含：名称、功能描述、触发时机、输入输出、阶段映射
4. 在 `examples/` 目录添加使用示例
5. 提交 PR，标题格式：`feat(skill): 新增 XxxSkill - 一句话描述`

### 修改阶段流程 / Modifying Stage Flow

1. 创建分支：`git checkout -b refactor/stage-X-description`
2. 修改 `SKILL.md` 中对应阶段的定义
3. 同步更新 `docs/` 目录下的 Word 审阅版文档
4. 在 PR 描述中说明修改理由和影响范围
5. 标题格式：`refactor(stage): 调整阶段X的xxx`

### PR 审查流程 / PR Review Process

1. 至少需要 1 位 Maintainer 审查通过
2. 所有 CI 检查必须通过
3. 文档变更需同步更新 Word 审阅版
4. 工具接口变更需在 CHANGELOG.md 中记录

---

## 许可证 / License

本项目采用 [MIT 许可证](LICENSE)。

---

> **Agent projects on GitHub solve "how to make Agents do things". Charter Orchestrator solves "how to govern Agents doing things."**
>
> Agent 的蛮荒时代即将结束，治理的时代正在开启。
>
> The Wild West of AI Agents is ending. The era of governance is beginning.
>
> ⭐ Star · 🍴 Fork · 👁 Watch · 参与讨论


## 🏭 v2.0 Production Layers

v2.0 closes the four production gaps named in the 2026 peer review:

| Layer | Module | What it does |
|---|---|---|
| **OTel + Grafana** | `charter/otel_export.py` | OTLP/JSON export, Prometheus metrics, Grafana dashboard template |
| **Agent Identity** | `charter/identity.py` | signed tool calls, anti-replay, capability-bound, stdlib-only (no `cryptography`) |
| **Vector Memory** | `charter/vector_memory.py` | semantic recall via hashing embedder (pluggable LLM backend) |
| **SOP Templates** | `charter/templates/` | finance / healthcare / e-commerce / research governance baselines |

22 automated tests (`python -m pytest tests/`) cover v1.1 + v2.0.
## v2.2 — Production Linkages

- **Online LLM-as-judge** — `charter/llm_judge_online.py`: real Agnes/OpenAI judge
  backends over stdlib HTTP; graceful offline fallback when no key / no network
  (tests stay green in CI). Drop-in for the offline heuristic judge.
- **Cross-session persistent memory** — `charter/session_store.py`: file-backed
  SQLite (`~/.charter/sessions.db`), WAL mode, multi-process-safe; semantic
  recall via pluggable embedder + recency + salience blend; cross-session
  `query()` surfaces what prior sessions learned.
- **Full OTel → Jaeger / Tempo link** — `charter/trace_link.py`: retry-safe
  OTLP/JSON exporters to Jaeger/Tempo, read-back query, per-service SLO digest
  (p50/p95 latency, error rate, RPS) with boolean SLO-MET/BREACHED verdict.

Install: `pip install charter-orchestrator` (stdlib-only core). Optional extras:
`[crypto]` (X.509/mTLS), `[llm]` (HTTP embedders + online judge).
## v2.3 — Production Linkage Hardening

- **Real mTLS** — `charter/mtls.py`: server-side cert verification against a
  `TrustAnchor` (chain + EKU + validity + revocation + CA signature), with a
  simplified PEM-metadata fallback when `cryptography` is absent.
- **Template marketplace → GitHub PR** — `charter/github_pr.py`:
  `open_template_pr(...)` validates a candidate SOP template and opens a (draft)
  PR on GitHub via REST; offline-safe (no token → returns a fully-prepared
  draft payload instead of raising).
- **Production embedding endpoint + cache** — `charter/embed_cache.py`:
  two-level (LRU + SQLite) cache wrapping the Agnes/OpenAI embedders;
  `production_embedder(...)` auto-detects the key and falls back to the
  offline hashing embedder so CI stays green.
- **SPIFFE / PKI-issued identity** — `charter/spiffe.py`: SPIFFE ID grammar,
  trust-domain CA, SVID issuance with URI SAN, `verify_svid` / `bundle_svid`
  for mTLS presentation.
## v2.4 — Multi-System Linkages

- **Multi-model judge consensus** — `charter/judge_consensus.py`: run N judge
  backends (Agnes + OpenAI, or N models), aggregate mean/median per-dimension
  scores, majority verdict, agreement matrix + confidence. Offline-safe
  (falls back to the heuristic judge when no live backends).
- **Cross-session memory compression** — `charter/memory_compress.py`:
  summarize a session's raw episodes into key facts + a one-line summary
  (LLM when a key is set, heuristic otherwise), re-store them with higher
  salience so future sessions recall the distilled knowledge.
- **Trace SLO → real alerting** — `charter/slo_alerts.py`: turn breached
  SLOs into Alertmanager / PagerDuty payloads; `fire(backend=...)` is
  retry-safe (carries the payload even when the endpoint is unreachable).
- **SPIFFE → real SPIRE Server** — `charter/spiffe_grpc.py`: gRPC gateway
  that fetches SVIDs from a live SPIRE `svid` service when a channel is
  bound, and falls back to the local `TrustDomain` issuer otherwise
  (same call shape, CI-safe).
- **Template PR auto-CI + community scoring** — `charter/pr_community.py`:
  `run_template_ci(spec)` runs the host repo's spec-integrity gate on a
  candidate template; `community_score` / `rank_templates` aggregate user
  helpful/adopted/reported signals into a weighted per-template score.
## v2.5 — Multi-System Linkages (Phase 2)

- **Multi-provider judge weighted voting** — `charter/judge_voting.py`:
  aggregate N provider judges with per-provider weights (default equal, or
  `accuracy_weights` from a labeled gold set); weighted mean per-dim +
  weighted majority verdict + effective agreement.
- **Hierarchical memory compression** — `charter/memory_hierarchy.py`:
  episode → session → project, three tiers; `compress_project` rolls session
  summaries into a rolling project digest, `recall_project` surfaces the
  right tier for a query.
- **Prometheus/Alertmanager rule auto-generation** —
  `charter/prometheus_rules.py`: emits a `rules.yaml` (SLO-aware error-rate,
  tool-burst, low-uptime expressions) + an Alertmanager provisioning
  skeleton (route + inhibit + receivers) ready to drop into Grafana.
- **SPIRE gRPC workload attestation** — `charter/spiffe_attestation.py`:
  build attestation requests (k8s_pod / workload_jwt / opaque), attest to a
  live SPIRE Server or fall back to the local issuer, verify the SVID.
- **Real GitHub PR comment scoring** — `charter/pr_comment_scoring.py`:
  fetch a PR's reviews/comments/reactions, fold into the community score,
  and an `auto_merge_gate` (conservative: requires live signals + min
  reviews).
- **Cross-repo multi-agent checkpoint sharing** —
  `charter/cross_repo.py`: a file-backed `~/.charter/checkpoints/` exchange;
  `publish_checkpoint` / `pull_checkpoint` / `list_published` /
  `import_into_core` so agents in different repos share governance state.
## v2.6 — Multi-System Linkages (Phase 3)

- **Concurrent judge voting + result cache** — `charter/judge_concurrency.py`:
  `vote_judges_concurrent` runs N provider judges on a thread pool;
  `JudgeResultCache` + `cached_vote` make repeated votes O(1).
- **Memory vector clustering** — `charter/memory_clustering.py`:
  threshold-based agglomerative clustering over embedded episodes;
  `cluster_session` collapses a session's raw episodes into K cluster
  summaries (K << N).
- **Mimir multi-tenant + label propagation** —
  `charter/mimir_multitenant.py`: per-project Mimir tenants, tenant-scoped
  SLO rules with propagated labels, Mimir distributor label-propagation
  config, Grafana Mimir/Loki/Tempo data sources — all as provisioning JSON.
- **Real k8s SPIRE Agent mTLS** — `charter/spire_k8s_mtls.py`:
  `render_spire_agent_config` (the JSON a real `spire-agent` reads),
  `render_agent_values` (k8s volumes + projected SA token + env),
  `mtls_env` (SPIFFE_ENDPOINT_SOCKET / SPIFFE_TLS_* flags).
- **PR comment LLM sentiment / specificity** — `charter/pr_sentiment.py`:
  `analyze_pr_comments` pulls a PR's review + issue comments and runs a
  pluggable LLM (or offline heuristic) sentiment / specificity / actionability
  analyzer; returns per-comment + aggregate `{avg_sentiment, avg_specificity,
  n_actionable, themes}`.
- **Team shared checkpoint storage (S3/GCS) + audit log** —
  `charter/checkpoint_shared.py`: `SharedCheckpointStore` publishes / pulls
  checkpoints to filesystem / S3 / GCS (auto-detects SDKs, degrades to local
  dir), writes every op to an append-only JSONL `AuditLog`;
  `publish_to_team` / `pull_from_team` / `audit_report` are the one-shot
  wrappers.
## v2.7 — Multi-System Linkages (Phase 4)

- **Distributed judge pool (K8s Job multi-replica)** — `charter/judge_pool.py`:
  `plan_judge_pool` builds N per-provider K8s Job replicas + a collector Job;
  `DistributedJudgePool.aggregate` groups replica votes per provider so a
  provider with 3 replicas doesn't triple its weight; `render_pool_manifests`
  emits the Job/ConfigMap/collector docs as JSON (offline-safe plan-only
  without a k8s client).
- **Memory LLM auto-naming** — `charter/cluster_naming.py`:
  `name_clusters` asks a pluggable LLM (or a deterministic
  `HeuristicClusterNamer` when no key) for a 1-3 word name + one-line
  description per cluster; `named_cluster_report` clusters + names a
  session's episodes and stores the *named* summaries back.
- **Mimir → Grafana OnCall alert routing** — `charter/oncall_routing.py`:
  `oncall_integrations` + `oncall_route_policy` map
  `{tenant, severity, alertname}` → a team's OnCall integration
  (Slack / PagerDuty / webhook) with per-severity escalation windows;
  `oncall_provisioning_bundle` emits the full routing config as JSON.
- **Real k8s SPIRE node-agent socket handshake** —
  `charter/spire_node_handshake.py`:
  `render_workload_socket_manifests` wires the node agent's socket into a
  pod (emptyDir + env + postStart ping); `validate_workload_socket` checks
  socket/bundle path consistency + DNS-safe trust domain; `handshake_plan`
  documents the connect→attest→fetch→verify→mTLS step sequence.
- **PR comment LLM auto-completion / rewrite** — `charter/pr_autosuggest.py`:
  `pr_autosuggest` + `autosuggest_pr_comments` propose concrete rewrites,
  follow-ups, and action items for vague / negative / actionable comments
  (LLM when a key is set, `HeuristicSuggester` otherwise).
- **S3 versioning + cross-region replication + team RBAC** —
  `charter/checkpoint_rbac.py`: `TeamRBAC` (owner/admin/member/viewer)
  gates publish/pull/import/audit; `s3_versioning_config` +
  `s3_cross_region_replication` emit the bucket-versioning + CRR JSON;
  `team_policies` bundles the RBAC table + versioning + CRR as one JSON.
## v2.8 — Multi-System Linkages (Phase 5)

- **Distributed judge pool on a real K8s cluster + S3 results + autoscale** —
  `charter/judge_pool_live.py`: `LiveJudgePool.create` applies the Job
  manifests to a live cluster (plan-only without a kubernetes client);
  `wait_and_collect` polls the collector Job + reads the aggregate from S3;
  `store_result_to_s3` persists it; `autoscaler_plan` emits a KEDA
  ScaledObject + an HPA fallback.
- **Multilingual auto-naming for memory clusters** —
  `charter/cluster_multilingual.py`: `detect_language` (script + stopword
  heuristic, no NLP dep) + `multilingual_name_clusters` (names each cluster
  in its detected language via a pluggable LLM / heuristic namer).
- **Grafana OnCall real delivery (gRPC / webhook)** —
  `charter/oncall_deliver.py`: `OnCallClient.deliver` POSTs to OnCall's API /
  a custom webhook / a gRPC bridge; `route_and_deliver` resolves the team and
  delivers in one call (offline-safe payload-only without a base URL).
- **Real k8s SPIRE node-agent bidirectional mTLS** —
  `charter/spire_bidir_mtls.py`: `BidirMTLSConfig` +
  `build_bidir_mtls_context` / `validate_bidir_mtls` (client + server SVIDs,
  mutual verify-peer SPIFFE IDs) + `render_bidir_k8s_values` + the
  two-way `attestation_exchange_plan`.
- **PR comment LLM diff-level code completion** —
  `charter/pr_diff_completion.py`: `complete_diff_hunks` turns a PR's hunks +
  review comments into concrete `before`/`after` code rewrites + rationale
  (pluggable LLM / heuristic).
- **Checkpoint RBAC → real IAM / S3 bucket policy** —
  `charter/checkpoint_iam.py`: `iam_policy` (per-role IAM docs) +
  `s3_bucket_policy` (deny-default + per-role allow with team tag) +
  `render_iam_bundle`, all JSON-ready for the AWS console / CLI.
## v2.9 — Multi-System Linkages (Phase 6)

- **Judge pool multi-trigger + cost-aware autoscaling** —
  `charter/judge_pool_cost.py`: `JudgePoolAutoscaler` plans a KEDA
  ScaledObject with multiple triggers (pending-task queue, Prometheus rule
  breach, calendar window, burst) and a **cost ceiling** that caps
  `maxReplicas` to a $ budget; `render_cost_autoscaler` emits the KEDA doc +
  a scale-decision table across budgets.
- **Cross-language automatic merging of memory clusters** —
  `charter/memory_cross_language.py`: `detect_topic_keywords` (CJK→roman
  technical-term table + Latin content words) so a zh "数据库连接池调优"
  cluster merges with an en "database connection pool tuning" cluster;
  `cross_language_merge` + `merge_cross_language` merge clusters across
  languages (keyword Jaccard or centroid cosine) into one.
- **Grafana OnCall real gRPC channel delivery** —
  `charter/oncall_grpc_deliver.py`: `OnCallGRPCClient.deliver` invokes the
  `oncall.OnCallService.Notify` RPC when a gRPC channel + stub are bound;
  `render_oncall_grpc_stubs` emits the service / method stubs + channel
  config. Offline-safe (plan-only without a channel).
- **k8s SPIRE bidirectional mTLS regression test** —
  `charter/spire_bidir_regression.py`: `MockNodeAgent` + `MockWorkload`
  drive the two-way handshake against a reference implementation;
  `run_bidir_mtls_regression` checks 6 invariants (both SVIDs under the
  trust domain, mutual verify-peer, same trust domain, socket under the
  mount).
- **PR diff cross-file + cross-hunk consistency** —
  `charter/pr_diff_consistency.py`: `CrossHunkConsistency.detect` catches
  unpropagated renames, removed definitions still used, and conflicting
  `after` blocks on the same hunk; `reconcile_hunks` applies the
  reconciliation (rename propagation, re-introduce, keep the longest);
  `cross_file_summary` is a per-file digest of the blast radius.
- **Checkpoint IAM real AWS apply + audit** —
  `charter/checkpoint_iam_apply.py`: `IamApplier.apply` creates the per-role
  IAM roles + attaches the policies + puts the S3 bucket policy via boto3
  (dry-run when no session); `IamAuditLog` records every mutation;
  `iam_drift_report` reads the live state.
## v3.0 — Multi-System Linkages (Phase 7)

- **Judge pool on a real K8s cluster + S3 + KEDA deployment** —
  `charter/judge_pool_deploy.py`: `JudgePoolDeployment` renders a
  `kubectl apply`-ready bundle (ConfigMap + N judge Jobs + collector +
  KEDA ScaledObject + an S3 result-key ConfigMap), a `kubectl` plan, and a
  post-deploy health probe (`verify_deployment`); `deploy` applies to a
  live cluster when a client is bound, plan-only otherwise.
- **Cross-language merging in true vector space** —
  `charter/memory_vector_merge.py`: `merge_in_vector_space` embeds each
  cluster's representative with a multilingual embedder (a real LLM
  embedding when a key is set, the offline hashing embedder otherwise) and
  merges clusters whose *centroid vectors* are close - a language-agnostic
  signal that catches same-topic cross-language pairs the keyword table
  can't.
- **OnCall real gRPC end-to-end** — `charter/oncall_grpc_e2e.py`:
  `OnCallGRPCE2E.connect` opens a real `grpc` channel (a `MockChannel`
  plan when grpc isn't installed) + binds the OnCall stub; `deliver`
  serializes the `Notify` request, invokes it, and returns a receipt;
  `e2e_delivery_report` is the one-shot verdict a CI / on-call pipeline
  asserts on.
- **k8s SPIRE bidirectional-mTLS real node-agent socket handshake** —
  `charter/spire_socket_handshake.py`: a `MockUnixSocket` pair models the
  `SPIFFE_ENDPOINT_SOCKET` Unix-domain socket; `BidirHandshake.run`
  drives the two-way SVID exchange (connect -> present -> verify-peer on
  both sides) and reports `mtls_established`.
- **PR diff consistency via LSP / tree-sitter** —
  `charter/pr_diff_semantics.py`: a `TreeSitterResolver` (real
  definition / use analysis when tree-sitter is installed, the v2.9
  identifier-heap as an offline fallback) + `semantic_check` catching
  cross-hunk slips by real symbol resolution.
- **Checkpoint IAM real AWS apply + auto drift remediation** —
  `charter/checkpoint_iam_remediate.py`: an `IamRemediator` controller
  (observe -> remediate -> re-check) that creates missing roles, upserts
  stale policies, and puts the bucket policy, with a JSONL audit trail;
  `reconcile_iam` is the one-shot reconcile (dry-run without a session).
