# v3.10.0 — MCP 工具结果推送附带 last_result 全文 + demo-skill watch --snapshot 持久化

发布日期：2026-09-15

## ① MCP 工具结果推送附带 last_result 全文（`charter/mcp_server.py`）

- 新增 `CharterMCPServer._tool_result_payload(tool_name)`：从 `_tool_results`
  （v3.9 引入的线程安全存储）构建与 `resources/read` 完全同构的 JSON 载荷
  （`found` / `ok` / `ts` / `result`），未调用过返回 `found=false` 说明。
- `_notify_tool_result_changed` 升级：每次 `tools/call` 触发的
  `notifications/resources/updated` 事件现携带 `last_result` 字段（完整结果），
  订阅者收到推送即可直接使用，**无需再发 `resources/read`** —— 这正是
  多 Agent 一致性架构分析中"事件溯源：状态由事件流派生、可追溯、解耦"
  的轻量落地（push 即携带最新快照）。
- 3 个新测试（推送携带全文 / 未调用返回 found=false / 推送载荷与 read 资源一致）

## ② demo-skill watch `--snapshot` 模式：watch 报告持久化 JSON（`charter/demo_skill.py`）

- 新增 `_snapshot_watch_report(report, path, promql=None, base_url=None,
  metadata=None)`：把本轮 watch 报告（SLO 历史、告警、OnCall/Alertmanager 投递
  receipt、Prometheus 查询）落盘为 JSON 快照，含 `snapshot_version` / `written_at` /
  `report` / 可选 `promql` / `base_url` / `metadata`。
  - 自动创建缺失父目录
  - 写失败不抛异常，返回 `{path, ok, bytes, error}`（报告仍可由调用方打印，不丢）
  - 契合多 Agent 一致性分析中"时间旅行调试 / 重放事件流复现 Bug"思想：
    持久化快照是时间点状态，供后续审计或回归 diff
- CLI 新增 `--snapshot PATH`（对 `--watch` 与 `--promql` 都生效）：
  ```bash
  python -m charter.demo_skill --watch --iterations 3 --slo-pct 90 \
      --snapshot ./audit/watch-$(date +%s).json
  python -m charter.demo_skill --promql 'error_rate' --prometheus-base http://prom:9090 \
      --prometheus-range --snapshot ./audit/promql-slo.json
  ```
- 5 个新测试（基础写盘 / 含 promql / 写失败不抛 / 自动建父目录 / CLI 端到端）

## 元数据
- `pyproject.toml` / `__init__.py` / SKILL.md / README → 3.10.0；导出 `_snapshot_watch_report`
- 总测试 394 → 402（+3 推送携带全文 +5 --snapshot +1 版本净增 +3 调整）
- 3.9 / 3.11 / 3.12 全绿

## 架构借鉴
本版本的两项功能对应《多Agent系统架构设计分析报告》中的进阶设计：
- ① 推送携带 last_result 全文 ≈ **事件溯源**（状态由事件流派生，订阅者解耦、可追溯）
- ② --snapshot 持久化 ≈ **时间旅行调试 / 重放**（时间点快照供审计、回归 diff）
后续 v3.11+ 候选可引入：Critic Agent 全局反思（前置校验+后置审计+动态修复）、
全链路语义追踪（输入输出语义相似度拦截幻觉）、小模型路由+语义缓存。
