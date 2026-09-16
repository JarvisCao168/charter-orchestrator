# Charter Orchestrator

> **AI Agent 全生命周期治理与编排框架**
>
> 定义 Agent 怎么干活、干到什么标准、什么时候该停下来让人确认
>
> 定义 Agent 怎么干活、干到什么标准、什么时候该停下来让人确认

[![Version](https://img.shields.io/badge/version-3.22.0-blue.svg)](https://github.com/JarvisCao168/charter-orchestrator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Skill 定义](https://img.shields.io/badge/Skill-v2.1.0-green.svg)](SKILL.md)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![平台](https://img.shields.io/badge/Platform-Agent--Independent-brightgreen.svg)](.)

---


## ⚡ 可执行 / Runnable (v1.1)

v1.1 把治理规范变成了可运行的 Python 包。5 分钟跑通：

```bash
git clone https://github.com/JarvisCao168/charter-orchestrator.git
cd charter-orchestrator
pip install -e .
python -m charter.cli demo     # 10 阶段 + 门禁 + TDD + Guardrails + 评估全跑通
```

- **可执行核心**：`charter/`（core、governance、observability、evaluation、memory）
- **10 个自动化测试**：`python -m pytest tests/`
- **快速上手**：[`docs/quickstart.md`](docs/quickstart.md)
- **故障覆盖证明**：[`docs/fault_coverage.md`](docs/fault_coverage.md)

## 🔄 MCP 服务器（v3.1）

Charter 现在自带 stdio MCP 服务器——把治理框架直接挂载到 Claude Code、Codex 或任意 MCP 客户端：
到 Claude Code、Codex 或任何 MCP 客户端：

```bash
pip install -e ".[mcp]"          # or: pip install charter-orchestrator[mcp]
python -m charter.mcp_server     # stdio JSON-RPC
```

**MCP 配置**（Claude Desktop / Codex / `.mcp.json`）：

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

- **20 个工具**：`init_project`、`advance_stage`、`confirm_gate`、
  `query_status`、`query_rule`、`list_skills`、`execute_in_sandbox`、
  `create_dropbox`、`manage_task_lifecycle`、`trigger_workflow`、
  `create_chat_chain`、`save_checkpoint`、`restore_checkpoint`、
  `dispatch_to_model`、`manage_worktree`、`enforce_tdd`、`guardrails`、
  `enable_autonomous_mode`、`trace_operation`、`query_trace`
- **47 个技能**作为 MCP 资源（`charter://skills/<id>`），每个带 I/O 契约
- **SKILL.md** 升级为 Anthropic 兼容的 YAML frontmatter（Claude Code 原生发现）


## 📦 v3.2 — 107 个技能 + MCP SSE/HTTP

- **技能：47 → 107** — 新增 60 个结构化技能，映射到 58 个 charter 模块
  （dev +8、security +8、obs +10、collab +8、analysis +6、test +6、deploy +8、tool +6）。
  每个技能都携带 `module` 字段，指向具体落地它的 Python 模块。
- **MCP SSE/HTTP 传输** — 可选的纯 stdlib HTTP+SSE 服务器，与默认 stdio 并存：
  stdio 传输：
  ```bash
  python -c "from charter.mcp_server import run_http_server; run_http_server('0.0.0.0', 8765)"
  # GET /mcp/health · GET /mcp/tools · GET /mcp/sse · POST /mcp/message?client=<cid>
  ```
- `scripts/validate_skills.py` 在 CI 中强制校验 107 技能不变量。
- 292 个测试，3.9 / 3.11 / 3.12 全绿。


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
  make demo-skill SKILL=obs_09          # SLO 越限 -> 告警 -> OnCall gRPC e2e
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

## 🔄 v3.22 — 自动注册 Sweeper + Webhook 持久化 + 自定义 Tier + 层级表格看板

- **`start_sweeper(http_server=...)` 自动注册**：传入 `HTTPMCPServer`
  实例即自动 `register_sweeper()`，`/metrics` 输出
  `charter_sweeper_sweeps_total` / `keys_swept_total` /
  `uptime_seconds` / `running`，免去手动接线。
- **Webhook 重试 SQLite 持久化**：`_webhook_set_db_path(path)` 启用
  崩溃安全落盘；`_webhook_restore_from_db()` 启动时恢复未发 webhook。
- **`make stress TIER=custom N=8 I=50`**：自定义档位，JSON 输出带
  `tier="custom"` + 实际 `n_writers`/`iterations` 参数。
- **看板 tier 分组渲染**：`metrics-watch` 解析 SSE `tier_breakdown`
  数据行，每 5 轮输出 per-tier gate_pass/fail 计数表格。
- **测试**：559 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.21 — Sweeper 统计 + Webhook 重试 + 压测 Tier + SSE 层级明细

- **`SweeperHandle.stats()`**：`{sweeps_total, keys_swept_total,
  uptime_s, running, last_sweep, last_reconcile}`；
  `HTTPMCPServer.register_sweeper(handle)` 接入 `/metrics`
  （`charter_sweeper_sweeps_total` / `keys_swept_total` /
  `uptime_seconds` / `running`）。
- **Webhook 重试队列**：`_WEBHOOK_RETRY_QUEUE` 内存队列 + 指数退避
  （2s→4s→8s，最多 3 次）；`audit-loop` 每周期自动 drain 重试。
- **`make stress TIER=high|low`**：high=16×100×50 / low=2×10×30；
  JSON 输出带 `tier` 字段。
- **SSE `tier_breakdown` 推送**：`/mcp/sse?stream=metrics` 事件附带
  `{tier: {gate_pass:<tool>: n, ...}}` 明细，看板按 tier 分组渲染。
- **测试**：553 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.20 — 后台 GC 线程 + Webhook 审计 + CI 压测校验 + 双标签指标

- **`start_sweeper()` 后台 GC**：`cache.start_sweeper(interval_s=30,
  reconcile=True)` 启动守护线程，周期执行 `sweep_expired()` + 可选
  `reconcile(repair=True)`；返回 handle（`stop()` / `last_sweep` /
  `last_reconcile` / `running`）。
- **`audit-loop --report-to-webhook`**：`--webhook-url` + `--webhook-template`
  支持 Slack/Discord/飞书 JSON 推送（纯 stdlib），失败不中断循环。
- **`validate-stress-report --ci`**：输出 `{"valid", "errors", "file",
  "fields_checked"}` 机器可读 JSON，供 GitHub Actions 解析。
- **`/metrics` tool+tier 双标签**：`charter_mcp_gate_pass_total{tool="...",
  tier="high"}`，从 `route_task`/`plan_pipeline` 结果提取路由层级，支持
  Prometheus 多维聚合查询。
- **测试**：546 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.19 — TTL 清扫 + 审计健康检查 + 压测校验 + 按工具治理指标

- **`sweep_expired()` TTL 清扫**：`SemanticCache.sweep_expired()` 定期
  清除 L1/L2/L3 中 TTL 过期键（L3 写 tombstone），返回清除明细
  （`l1_swept` / `l2_swept` / `l3_swept` / `swept`）。
- **`audit-loop` 健康检查 + `--dry-run`**：`--metrics-url` 每周期先
  GET 确认 server 在线，离线跳过并记录；`--dry-run` 只写报告不附 PR。
- **`validate-stress-report`**：`charter.cli validate-stress-report
  cas_report.json` 校验 9 个必需字段（类型 + 完整性），配合
  `make stress JSON=1 OUT=file.json` 做 CI artifact 校验。
- **按 tool 名治理指标**：`/metrics` 新增
  `charter_mcp_gate_fail_total{tool="..."}` 等 5 个带标签计数器，
  支持 Prometheus 多维查询；看板渲染 top-3 gate_fail 工具。
- **Bug fix**：`do_POST` 剥离 query string 后再匹配路径（`?client=x`
  不再 404）。
- **测试**：536 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.18 — 缓存自动对账修复 + 双源看板 + 周期审计 + 压测 JSON

- **`reconcile(repair=True)` 自动修复**：`in_storage_only` 键从 L3/L2 回填
  L1，TTL 过期键全层清除（`_purge_key`）；`in_memory_only` 键持久化到
  L2+L3。返回 `repaired` 明细 + `repairs` 计数。
- **`metrics-watch` 双源**：`--sse` 参数启用 SSE 事件流线程，实时推送
  `charter://metrics` 更新；主循环轮询 `/metrics` 作为后备。
- **`audit-loop` 周期审计**：`charter.cli audit-loop --pr 42 [--interval 30]
  [--cycles 0]`，每周期跑 `demo --gov --trace-out` 并自动附到 PR。
- **`make stress JSON=1` / `OUT=file.json`**：压测结果输出为机器可读 JSON，
  供 CI artifact 归档。
- **测试**：526 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.17 — 治理审计仪表盘 + PR 审计 + 参数化 CAS + 缓存对账

- **治理审计仪表盘**：`python -m charter.cli metrics-watch --url
  http://host:port/metrics` 终端看板，轮询 5 个治理指标（gate pass/fail、
  tracer spans/hallucinations/drift）并显示每轮 Δ。
- **审计报告进 PR**：`charter.cli attach-audit --report gov_audit.json --pr
  123`：`--trace-out` 报告以 JSON 代码块附到 GitHub PR comment（优先
  `gh` CLI，回退 REST + `CHARTER_GITHUB_TOKEN`）。
- **CAS 压测参数化**：`stress_multi_writer` 输出 `ops` / `conflict_rate` /
  `wall_s`；`make stress-big`（16 写者 × 100 轮，50 次 CAS 重试）大压力档。
- **缓存对账**：`SemanticCache.reconcile()` 扫描 L1/L2/L3 键集差异
  （`in_memory_only` / `in_storage_only` / `consistent`）；
  `HTTPKeyValueBackend.list_keys()` + 参考网关 `/kv/_keys`。
- **测试**：520 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.16 — CAS 压测进 CI + 审计回放 + 共享 pipeline L3 + 治理审计指标

- **多写者 CAS 压测进 CI**：`make stress`（默认 4 写者 × 25 轮，断言无丢失
  更新）；`make stress-ci` 打印可直接粘贴的**非阻塞** Actions step
  （`continue-on-error: true`）；`test_cas_stress_no_lost_updates` 进 pytest。
- **SemanticTrace 审计回放**：`tracer.to_json()` / `export(path)` +
  `export_audit_report()`：自包含 JSON 审计时间线（summary + 每个 span 的
  id/ts/tool/相似度/verdict/文本）；`charter.cli demo --gov --trace-out
  file.json` 一键出报告。
- **plan_pipeline 共享 L3（跨进程）**：`demo --gov --live-pipeline`：参考
  KV 网关承载 pipeline 决策缓存 L3，两个独立 python 子进程跑同一计划，
  node-b 命中 node-a 的写入（`cached: True`，两侧 routing 完整）；缓存 key
  排除 per-call outputs，保证确定性命中。
- **治理审计指标**：`attach_full_governance` 后每次 `tools/call` 发布
  `charter_mcp_gate_pass_total` / `gate_fail_total` / `tracer_spans_total`
  / `tracer_hallucinations_total` / `tracer_drift_sum`（`/metrics` Prometheus 文本）。
- **测试**：514 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.15 — ETag CAS + 计划流水线缓存 + 全工具治理审计 + 真跨进程 live

- **ETag 式 CAS**：`put_if_version` 升级为 412 Precondition Failed 语义；
  `HTTPKeyValueBackend.cas(key, read, write_fn)` 观测-写入 CAS 循环 +
  `observe()` 单 GET 原子快照（消除值/版本两次读之间的竞态窗口）；
  `reference_kv_gateway()` 参考网关 + `stress_multi_writer()` 多写者压测
  （验证无丢失更新）。
- **plan_pipeline 决策缓存**：按 plan BLAKE2b 哈希缓存完整结果（critic 结论
  + 逐步路由），同计划秒级复用；`configure_pipeline_cache(disk_path,
  remote, ttl_s)` 可接 L2/L3。
- **全工具治理审计**：`attach_full_governance(server)` 把 25 个 MCP 工具
  全部自动经 ValidationGateway + SemanticTracer；修复 `tools/call` 追踪器
  引用未赋值 `text` 的潜伏 NameError。
- **`demo --gov --live` 真跨进程**：起真实 KV 网关 + 两个独立 python
  子进程（写/读），reader 进程经 L3 命中（hits: 1）。
- **版本断言防复发**：`test_version_is_v3_5` 改为动态读 `pyproject.toml`
  版本（正则扫描，3.9 兼容），今后升版本不会再打破 CI。
- **测试**：509 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.14 — 计划流水线 + 自愈闭环 + L3 一致性

- **`plan_pipeline` MCP 工具**（24 -> 25）：一次调用完成 "Critic 审查计划
  DAG（可选闭环修复）→ 对最终计划每步做模型路由" 的完整流水线；步骤深度
  按 DAG 传递祖先计算，`depth_scale`/`default_risk`/`default_tokens` 塑形
  TaskProfile。
- **自愈智能体闭环（`executor="mcp"`）**：`repair_and_rerun(plan,
  executor="mcp")` 默认把 agent 钩子绑定到 `run_tool` —— 修复后的每个
  MCP 工具步真实重跑，再进入下一轮后审，形成 "批评 → 修复 → 重跑真实工具
  → 重审" 的完整自愈链；`mcp_step_executor()` 顶层导出。
- **L3 分布式一致性**：`SemanticCache(ttl_s=...)` 按 key 过期；远端写带
  版本戳 `{"__v", "__ts", "value"}`，`get_version(request)` 返回最后写入
  版本（乐观锁令牌）；`HTTPKeyValueBackend.put_if_version(key, value,
  if_version)` 经 `X-If-Version` 头做乐观写（409 冲突 → False，离线安全）。
- **`demo --gov --live`**：起真实 in-process HTTP KV 网关，演示跨进程 L3
  命中（node1 写版本化值，node2 空内存经 L3 读回且版本可见）。
- **测试**：502 全绿（3.9 / 3.11 / 3.12）。

## 🔄 v3.13 — 治理 MCP 工具 + Critic 重跑闭环 + 分布式语义缓存

- **4 个治理 MCP 工具**（`validate_output` / `critic_plan` / `trace_span` /
  `route_task`，20 -> 24）：四大治理模块（校验网关 / 批评者 / 语义追踪 / 模型路由）
  直接暴露为 MCP 工具，`skills/gov_05..08` + manifest 115 条目。
- **Critic repair-rerun 智能体闭环**：`repair_and_rerun(plan, executor,
  max_rounds)` — reflect → 修复 → **智能体重跑** → 重审 完整循环；
  `executor(step)` 驱动逐步重跑，异常记录不传播；无 executor 时退化为
  `reflect_until_sound`（纯 plan 修复）。
- **分布式 SemanticCache**：三级 L1 内存 → L2 SQLite → L3 远端后端；
  `HTTPKeyValueBackend`（纯 stdlib，离线安全：网络错误降级为 miss）+
  `make_remote_backend(kind, base_url)` 工厂（`http`/`kv`/`redis`/`postgres`/
  `memcached`/`null` 统一经 HTTP KV 网关）。
- **`charter.cli demo --gov`**：四模块链 + 两种闭环模式的端到端治理演示。
- **测试**：492 全绿（3.9 / 3.11 / 3.12）；新增 `test_gov_mcp_tools` /
  `test_critic_repair_rerun` / `test_semantic_cache_remote` / `test_v3_13`。

## 🔄 v3.12 — Critic 修复后重跑闭环 + SemanticCache 持久化落盘

- **Critic 自愈闭环**：`Critic.apply_repairs(plan, repairs)` 把修复补丁注入 plan
  （insert_step / break_cycle / dedupe_artifact，原 plan 不改动）；
  `Critic.reflect_until_sound(plan, outputs, max_rounds)` 闭环驱动——
  reflect → 注入补丁 → 重跑，直到 plan 结构 sound 或达上限。`CriticReport`
  新增 `rounds` / `history` / `converged` / `final_plan` 字段，"报错"真正变"自愈"。
- **SemanticCache 持久化**：`SemanticCache(disk_path=...)` 升级为两级缓存
  （内存 LRU + SQLite 落盘，复用 `embed_cache` 的 SQLite store 模式）；
  `put` 同步写盘、`get` 内存 miss 回查磁盘并回填，实现**跨进程语义缓存**降本。
  新增 `close()` / `is_persistent()` / `stats()["disk_enabled"]`。
  ```python
  cache = SemanticCache(disk_path="./cache/semantic.sqlite")
  cache.put("q1-growth-rate", 0.12)
  cache.close()
  # 新进程
  cache2 = SemanticCache(disk_path="./cache/semantic.sqlite")
  cache2.get("q1 growth rate")  # -> 0.12 (跨进程命中)
  ```
- 469 测试（原 455 + 7 Critic 闭环 + 5 SemanticCache 持久化 + 2 版本调整），3.9 / 3.11 / 3.12 全绿。

## 目录

- [概述](#概述)
- [核心能力](#核心能力)
- [架构总览](#架构总览)
- [快速开始](#快速开始)
- [工具一览](#工具一览)
- [Skills 工具箱](#skills-工具箱)
- [治理规则体系](#治理规则体系)
- [6 道防线](#6-道防线)
- [自动驾驶模式](#自动驾驶模式)
- [外部集成](#外部集成)
- [版本路线图](#版本路线图)
- [商业化](#商业化)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 概述

Charter Orchestrator 是一个 **"治理 + 流程 + 工具"** 三位一体的智能体编排框架。它在整合 GitHub Squad、ChatDev、GitHub Agentic Workflows、OpenHands 等项目核心优势的基础上，经过对 LangGraph、CrewAI、AG2、OpenAI Agents SDK、autonomous-dev-team、agent-skills、Superpowers、Orchestrator 等 10+ 个同类项目的深度竞品分析，实现了从"流程编排框架"到"企业级智能体治理平台"的全面跃迁。

### 一句话定位

> GitHub 上现有的 Agent 项目解决的是 **"怎么让 Agent 做事"**（引擎/工具/执行），而 Charter Orchestrator 解决的是 **"怎么管理 Agent 做事"**（治理/流程/规则）—— 它是 **Agent 之上的管理层**，而非 Agent 本身。

### 类比理解

| 类比 | 说明 |
|------|------|
| 容器 vs Kubernetes | Agent frameworks (LangGraph/CrewAI) are containers; Charter Orchestrator is K8s |
| 工具 vs 宪法 | Agent is the tool; governance rules are the constitution |
| 引擎 vs 自动驾驶系统 | Agent is the engine; Charter Orchestrator is the autopilot ensuring safe driving |

---

## 核心能力

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

## 架构总览

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

## 快速开始

### 前置条件

- 智能体平台支持 Skill 机制（如 Hermes）
- 将 `SKILL.md` 部署到平台的 Skills 目录

### 第一步：初始化项目

对智能体发出以下指令：

对智能体发出以下指令：

```
请调用 init_project 工具，初始化以下项目：
- 项目名称：电商智能客服自动化
- 项目类型：software_dev
- 核心目标：搭建基于大模型的智能客服系统，支持多轮对话、工单自动分类、知识库检索增强
```

### 第二步：推进阶段

初始化完成后，按阶段逐步推进：

项目初始化完成后，按阶段逐步推进：

```
请调用 advance_stage 工具，推进到阶段一（需求分析）。
```

### 第三步：查询状态

随时了解项目进度：

随时了解项目进度：

```
请调用 query_status 工具，展示当前项目全貌。
```

### 第四步：查询规则

遇到合规疑问时：

遇到合规疑问时：

```
请调用 query_rule 工具，查询"安全红线"相关条款。
```

### 进阶：启用自动驾驶模式 (v1.0)

对于中低风险项目，可启用自动驾驶模式——一次审批后自主运行多个阶段：

对于中低风险项目，可启用自动驾驶模式，一次审批后自主运行：

```
请调用 enable_autonomous_mode 工具：
- 项目ID：your-project-id
- 起始阶段：stage_5
- 结束阶段：stage_7
- 审批级别：standard
```

---

## 工具一览

### 基础工具 (v1.0)

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

> **GitHub 上的 Agent 项目解决"怎么让 Agent 干活"。Charter Orchestrator 解决"怎么治理 Agent 干活"。**
>
> Agent 的蛮荒时代即将结束，治理的时代正在开启。
>
> AI Agent 的蛮荒时代即将结束，治理的时代正在开启。
>
> ⭐ Star · 🍴 Fork · 👁 Watch · 参与讨论


## 🏭 v2.0 生产层

v2.0 补齐 2026 同行评审指出的四个生产缺口：

| 层 | 模块 | 功能 |
|---|---|---|
| **OTel + Grafana** | `charter/otel_export.py` | OTLP/JSON 导出、Prometheus 指标、Grafana 仪表盘模板 |
| **Agent 身份** | `charter/identity.py` | 签名工具调用、防重放、能力绑定、纯 stdlib（无 `cryptography`） |
| **向量记忆** | `charter/vector_memory.py` | 基于哈希 embedder 的语义召回（可插拔 LLM 后端） |
| **SOP 模板** | `charter/templates/` | 金融 / 医疗 / 电商 / 科研治理基线 |

22 个自动化测试（`python -m pytest tests/`）覆盖 v1.1 + v2.0。
## v2.2 — 生产级联动

- **在线 LLM-as-judge** — `charter/llm_judge_online.py`：真实的 Agnes/OpenAI 评审
  后端（stdlib HTTP）；无 key / 无网络时优雅离线回退
  （CI 测试保持全绿）。可直接替换离线启发式评审。
- **跨会话持久记忆** — `charter/session_store.py`：文件支持的
  SQLite（`~/.charter/sessions.db`），WAL 模式，多进程安全；可插拔 embedder + 时效性 + 显著性融合的语义
  召回；跨会话
  `query()` 浮现先前会话学到的内容。
- **完整 OTel → Jaeger / Tempo 链路** — `charter/trace_link.py`：带重试的
  OTLP/JSON 导出器到 Jaeger/Tempo，读回查询，按服务 SLO 摘要
  （p50/p95 延迟、错误率、RPS），带布尔 SLO-MET/BREACHED 结论。

安装：`pip install charter-orchestrator`（纯 stdlib 核心）。可选扩展：
`[crypto]`（X.509/mTLS）、`[llm]`（HTTP embedder + 在线评审）。
## v2.3 — 生产级联动强化

- **真实 mTLS** — `charter/mtls.py`：服务端证书验证对照
  `TrustAnchor`（链 + EKU + 有效期 + 吊销 + CA 签名）；无 `cryptography` 时
  回退到简化 PEM 元数据校验。
- **模板市场 → GitHub PR** — `charter/github_pr.py`：
  `open_template_pr(...)` 校验候选 SOP 模板并通过 REST 在 GitHub 上开（草稿）
  PR；离线安全（无 token → 返回已备好的
  草稿 payload，而非抛异常）。
- **生产级 embedding 端点 + 缓存** — `charter/embed_cache.py`：
  两级（LRU + SQLite）缓存，包裹 Agnes/OpenAI embedder；
  `production_embedder(...)` 自动检测 key，无 key 时回退到
  离线哈希 embedder，CI 保持全绿。
- **SPIFFE / PKI 签发身份** — `charter/spiffe.py`：SPIFFE ID 语法、
  信任域 CA、带 URI SAN 的 SVID 签发，`verify_svid` / `bundle_svid`
  用于 mTLS 展示。
## v2.4 — 多系统联动

- **多模型评审共识** — `charter/judge_consensus.py`：运行 N 个评审
  后端（Agnes + OpenAI，或 N 个模型），按维度聚合均值/中位数
  得分、多数决结论、一致性矩阵 + 置信度。离线安全
  （无实时后端时回退到启发式评审）。
- **跨会话记忆压缩** — `charter/memory_compress.py`：
  将会话原始 episode 归纳为关键事实 + 一行摘要
  （有 key 走 LLM，否则启发式），以更高显著性重新存回
  供未来会话召回蒸馏知识。
- **Trace SLO → 真实告警** — `charter/slo_alerts.py`：将越限
  SLO 转成 Alertmanager / PagerDuty payload；`fire(backend=...)`
  重试安全（端点不可达时仍携带 payload）。
- **SPIFFE → 真实 SPIRE Server** — `charter/spiffe_grpc.py`：gRPC 网关，
  绑定 channel 时从活的 SPIRE `svid` 服务拉 SVID，否则回退到
  本地 `TrustDomain` 签发方
  （同一调用形态，CI 安全）。
- **模板 PR 自动 CI + 社区评分** — `charter/pr_community.py`：
  `run_template_ci(spec)` 在候选模板上跑宿主仓库的 spec 完整性门禁；`community_score` /
  `rank_templates` 把用户 helpful/adopted/reported 信号聚合成按模板加权得分。
  信号为按模板加权得分。
## v2.5 — 多系统联动（第二阶段）

- **多提供商评审加权投票** — `charter/judge_voting.py`：
  按提供商权重聚合 N 个评审（默认等权，或
  来自标注 gold 集的 `accuracy_weights`）；按维度加权均值 +
  加权多数决结论 + 有效一致性。
- **分层记忆压缩** — `charter/memory_hierarchy.py`：
  episode → session → project，三层；`compress_project` 将 session
  摘要滚入 project 滚动摘要，`recall_project` 按查询浮现
  正确层级。
- **Prometheus/Alertmanager 规则自动生成** —
  `charter/prometheus_rules.py`：产出 `rules.yaml`（SLO 感知的错误率、
  工具爆发、低可用性表达式）+ 可即插 Grafana 的 Alertmanager 部署
  骨架（route + inhibit + receivers）。
- **SPIRE gRPC 工作负载证明** — `charter/spiffe_attestation.py`：
  构造证明请求（k8s_pod / workload_jwt / opaque），向活的
  SPIRE Server 做证明或回退到本地签发方，校验 SVID。
- **真实 GitHub PR 评论评分** — `charter/pr_comment_scoring.py`：
  拉取 PR 的 reviews/comments/reactions，并入社区评分；
  以及 `auto_merge_gate`（保守：要求实时信号 + 最少
  评审数）。
- **跨仓库多 agent checkpoint 共享** —
  `charter/cross_repo.py`：文件支持的 `~/.charter/checkpoints/` 交换区；
  `publish_checkpoint` / `pull_checkpoint` / `list_published` /
  `import_into_core`，让不同仓库的 agent 共享治理状态。
## v2.6 — 多系统联动（第三阶段）

- **并发评审投票 + 结果缓存** — `charter/judge_concurrency.py`：
  `vote_judges_concurrent` 在线程池上并行跑 N 个提供商评审；
  `JudgeResultCache` + `cached_vote` 让重复投票 O(1)。
- **记忆向量聚类** — `charter/memory_clustering.py`：
  对嵌入 episode 做基于阈值的凝聚式聚类；
  `cluster_session` 将 session 原始 episode 折叠为 K 个集群
  摘要（K << N）。
- **Mimir 多租户 + 标签传播** —
  `charter/mimir_multitenant.py`：按 project 划分 Mimir 租户，租户范围内的
  SLO 规则带传播标签，Mimir distributor 标签传播
  配置，Grafana Mimir/Loki/Tempo 数据源——全部以 provisioning JSON 产出。
- **真实 k8s SPIRE Agent mTLS** — `charter/spire_k8s_mtls.py`：
  `render_spire_agent_config`（真实 `spire-agent` 读的 JSON）、
  `render_agent_values`（k8s volumes + projected SA token + env）、
  `mtls_env`（SPIFFE_ENDPOINT_SOCKET / SPIFFE_TLS_* 标志）。
- **PR 评论 LLM 情感 / 具体度** — `charter/pr_sentiment.py`：
  `analyze_pr_comments` 拉 PR 的 review + issue 评论，跑可插拔的 LLM
  （或离线启发式）情感 / 具体度 / 可行动性
  分析器；返回按评论 + 聚合 `{avg_sentiment, avg_specificity,
  n_actionable, themes}`。
- **团队共享 checkpoint 存储（S3/GCS）+ 审计日志** —
  `charter/checkpoint_shared.py`：`SharedCheckpointStore` 发布 / 拉取
  checkpoint 到文件系统 / S3 / GCS（自动探测 SDK，降级到本地
  目录），每次操作写入追加式 JSONL `AuditLog`；
  `publish_to_team` / `pull_from_team` / `audit_report` 是一步
  包装器。
## v2.7 — 多系统联动（第四阶段）

- **分布式评审池（K8s Job 多副本）** — `charter/judge_pool.py`：
  `plan_judge_pool` 构建 N 个按提供商的 K8s Job 副本 + 收集器 Job；
  `DistributedJudgePool.aggregate` 按提供商分组副本投票，避免
  3 副本的提供商三倍权重；`render_pool_manifests`
  以 JSON 输出 Job/ConfigMap/收集器文档（无 k8s client 时
  离线 plan-only）。
- **记忆 LLM 自动命名** — `charter/cluster_naming.py`：
  `name_clusters` 让可插拔 LLM（无 key 时确定性
  `HeuristicClusterNamer`）为每个集群给 1-3 词名 + 一行
  描述；`named_cluster_report` 对 session episode 聚类 + 命名
  并回存*带名*摘要。
- **Mimir → Grafana OnCall 告警路由** — `charter/oncall_routing.py`：
  `oncall_integrations` + `oncall_route_policy` 把
  `{tenant, severity, alertname}` 映射到团队的 OnCall 集成
  （Slack / PagerDuty / webhook），带按严重度升级窗口；
  `oncall_provisioning_bundle` 以 JSON 输出完整路由配置。
- **真实 k8s SPIRE node-agent socket 握手** —
  `charter/spire_node_handshake.py`：
  `render_workload_socket_manifests` 把 node agent socket 接入 pod
  （emptyDir + env + postStart ping）；`validate_workload_socket` 检查
  socket/bundle 路径一致性 + DNS 安全信任域；`handshake_plan`
  文档化 connect→attest→fetch→verify→mTLS 步骤序列。
- **PR 评论 LLM 自动补全 / 改写** — `charter/pr_autosuggest.py`：
  `pr_autosuggest` + `autosuggest_pr_comments` 为模糊 / 负面 / 可行动评论
  提出具体改写、
  后续行动与行动项（有 key 走 LLM，否则 `HeuristicSuggester`）。
- **S3 版本化 + 跨区复制 + 团队 RBAC** —
  `charter/checkpoint_rbac.py`：`TeamRBAC`（owner/admin/member/viewer）
  门控 publish/pull/import/audit；`s3_versioning_config` +
  `s3_cross_region_replication` 输出 bucket 版本化 + CRR JSON；
  `team_policies` 把 RBAC 表 + 版本化 + CRR 打包为一个 JSON。
## v2.8 — 多系统联动（第五阶段）

- **真实 K8s 集群上的分布式评审池 + S3 结果 + 自动扩缩** —
  `charter/judge_pool_live.py`：`LiveJudgePool.create` 将 Job
  manifest 应用到活的集群（无 kubernetes client 时 plan-only）；
  `wait_and_collect` 轮询收集器 Job + 从 S3 读聚合结果；
  `store_result_to_s3` 持久化；`autoscaler_plan` 输出 KEDA
  ScaledObject + HPA 回退。
- **记忆集群多语言自动命名** —
  `charter/cluster_multilingual.py`：`detect_language`（文字 + 停用词
  启发式，无 NLP 依赖）+ `multilingual_name_clusters`（按检测到的语言
  用可插拔 LLM / 启发式命名器为每个集群命名）。
- **Grafana OnCall 真实投递（gRPC / webhook）** —
  `charter/oncall_deliver.py`：`OnCallClient.deliver` POST 到 OnCall API /
  自定义 webhook / gRPC 桥；`route_and_deliver` 一次调用解析团队并
  投递（无 base URL 时离线安全 payload-only）。
- **真实 k8s SPIRE node-agent 双向 mTLS** —
  `charter/spire_bidir_mtls.py`：`BidirMTLSConfig` +
  `build_bidir_mtls_context` / `validate_bidir_mtls`（客户端 + 服务端 SVID、
  互验 SPIFFE ID）+ `render_bidir_k8s_values` +
  双向 `attestation_exchange_plan`。
- **PR 评论 LLM diff 级代码补全** —
  `charter/pr_diff_completion.py`：`complete_diff_hunks` 把 PR 的 hunk +
  评审评论转成具体 `before`/`after` 代码改写 + 理由
  （可插拔 LLM / 启发式）。
- **Checkpoint RBAC → 真实 IAM / S3 bucket 策略** —
  `charter/checkpoint_iam.py`：`iam_policy`（按角色的 IAM 文档）+
  `s3_bucket_policy`（默认拒绝 + 按角色放行带团队标签）+
  `render_iam_bundle`，全部 JSON-ready 供 AWS 控制台 / CLI 使用。
## v2.9 — 多系统联动（第六阶段）

- **评审池多触发器 + 成本感知自动扩缩** —
  `charter/judge_pool_cost.py`：`JudgePoolAutoscaler` 规划带多个触发器的 KEDA
  ScaledObject（待处理任务队列、Prometheus 规则
  越限、日历窗口、突发），带**成本上限**限制
  `maxReplicas` 到 $ 预算；`render_cost_autoscaler` 输出 KEDA 文档 +
  跨预算的扩缩决策表。
- **记忆集群跨语言自动合并** —
  `charter/memory_cross_language.py`：`detect_topic_keywords`（CJK→拉丁
  术语表 + 拉丁内容词），使中文"数据库连接池调优"
  集群与英文 "database connection pool tuning" 集群合并；
  `cross_language_merge` + `merge_cross_language` 跨
  语言合并集群（关键词 Jaccard 或质心余弦）。
- **Grafana OnCall 真实 gRPC channel 投递** —
  `charter/oncall_grpc_deliver.py`：`OnCallGRPCClient.deliver` 在 gRPC channel + stub 绑定时
  调用 `oncall.OnCallService.Notify` RPC；
  `render_oncall_grpc_stubs` 输出服务 / 方法 stub + channel
  配置。离线安全（无 channel 时 plan-only）。
- **k8s SPIRE 双向 mTLS 回归测试** —
  `charter/spire_bidir_regression.py`：`MockNodeAgent` + `MockWorkload`
  对照参考实现驱动双向握手；
  `run_bidir_mtls_regression` 检查 6 个不变量（双方 SVID 位于
  同一信任域下、互验 peer、同一信任域、socket 位于
  mount 下）。
- **PR diff 跨文件 + 跨 hunk 一致性** —
  `charter/pr_diff_consistency.py`：`CrossHunkConsistency.detect` 捕捉
  未传播的重命名、被删除但仍被引用的定义、以及同一 hunk 上冲突的
  `after` 块；`reconcile_hunks` 应用
  对账（重命名传播、重新引入、保留最长）；
  `cross_file_summary` 是按文件的爆炸半径摘要。
- **Checkpoint IAM 真实 AWS 应用 + 审计** —
  `charter/checkpoint_iam_apply.py`：`IamApplier.apply` 通过 boto3 创建按角色的
  IAM 角色 + 附加策略 + 设置 S3 bucket 策略
  （无 session 时 dry-run）；`IamAuditLog` 记录每次变更；
  `iam_drift_report` 读取实时状态。
## v3.0 — 多系统联动（第七阶段）

- **真实 K8s 集群 + S3 + KEDA 部署的评审池** —
  `charter/judge_pool_deploy.py`：`JudgePoolDeployment` 渲染
  可 `kubectl apply` 的包（ConfigMap + N 个评审 Job + 收集器 +
  KEDA ScaledObject + S3 结果 key ConfigMap）、`kubectl` 计划、
  部署后健康探针（`verify_deployment`）；`deploy` 在绑定 client 时
  应用到活集群，否则 plan-only。
- **真实向量空间的跨语言合并** —
  `charter/memory_vector_merge.py`：`merge_in_vector_space` 用多语言 embedder
  嵌入每个集群的代表（设 key 走真实 LLM
  嵌入，否则离线哈希 embedder），
  合并*质心向量*相近的集群——一个语言无关的
  信号，捕捉关键词表无法覆盖的同主题跨语言对
  。
- **OnCall 真实 gRPC 端到端** — `charter/oncall_grpc_e2e.py`：
  `OnCallGRPCE2E.connect` 打开真实 `grpc` channel（未装 grpc 时用 `MockChannel`
  计划）+ 绑定 OnCall stub；`deliver`
  序列化 `Notify` 请求、调用并返回回执；
  `e2e_delivery_report` 是 CI / on-call 流水线
  断言的一步判定。
- **k8s SPIRE 双向 mTLS 真实 node-agent socket 握手** —
  `charter/spire_socket_handshake.py`：一对 `MockUnixSocket` 模拟
  `SPIFFE_ENDPOINT_SOCKET` Unix domain socket；`BidirHandshake.run`
  驱动双向 SVID 交换（双方 connect -> present -> verify-peer）
  并报告 `mtls_established`。
- **经 LSP / tree-sitter 的 PR diff 一致性** —
  `charter/pr_diff_semantics.py`：`TreeSitterResolver`（装了 tree-sitter 时做真实
  定义 / 使用分析，否则用 v2.9
  标识符堆做离线回退）+ `semantic_check`
  用真实符号解析捕捉跨 hunk 疏漏。
- **Checkpoint IAM 真实 AWS 应用 + 自动漂移修复** —
  `charter/checkpoint_iam_remediate.py`：`IamRemediator` 控制器
  （observe -> remediate -> re-check）创建缺失角色、upsert
  过期策略、设置 bucket 策略，带 JSONL 审计轨迹；
  `reconcile_iam` 是一步对账（无 session 时 dry-run）。
