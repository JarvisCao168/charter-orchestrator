# v3.9.0 — MCP 工具结果 read 侧 + demo-skill watch --promql 区间聚合模式

发布日期：2026-09-15

## ① MCP 工具结果 read 侧（`charter/mcp_server.py`）

- `CharterMCPServer` 新增 `_tool_results` 存储（线程安全 dict，tool_name → 最后一次结果）：
  每次 `tools/call` 执行后自动记录最新结果（含 `result` / `ok` / `ts`）。
- `resources/read` 新增支持 `charter://tools/<name>/result`：
  - 已调用过该 tool → 返回 JSON（`{"found": true, "ok", "ts", "result"}`）
  - 未调用过 → 返回 `{"found": false, "note": "no tool result yet"}`
  - mimeType `application/json`
- 补齐 v3.8 工具结果 resource 的 read 侧（v3.8 只有 push 侧）：订阅者可在收到
  `resources/changed` 推送后，用 `resources/read` 读取最新结果。
- 3 个新测试（调用前 read / 调用后 read / 不同 tool 隔离）

## ② demo-skill watch `--promql` 区间聚合模式（`charter/demo_skill.py`）

- 新增 `_query_prometheus_range(base_url, promql, start, end, step, _query=None)`：
  - 默认走 stdlib `urllib` GET `{base_url}/api/v1/query_range`
  - `_query` seam 可注入测试桩（签名：`fn(base_url, promql, start, end, step)`)
- 新增 `_aggregate_range_values(qres, agg)`：把区间查询结果的多值序列聚合成单点标量
  - `agg` 支持 `"avg"` / `"max"` / `"min"` / `"sum"` / `"p95"`（nearest-rank）
- `run_watch_from_promql(..., range_mode, range_window, range_step, range_agg)`：
  - `range_mode=True` 时，每轮查 `[now-window, now]` 的 `query_range`，用
    `_aggregate_range_values` 聚合成单点，再交给 `threshold_fn` 判 SLO
  - 报告 mode 标记为 `"promql-range"`，历史含 `range_agg` / `range_window` 字段
- CLI 新增 flag：
  ```bash
  python -m charter.demo_skill --promql 'error_rate' --prometheus-base http://localhost:9090 \
      --prometheus-range --prometheus-range-window 5m --prometheus-range-step 60s \
      --prometheus-range-agg p95 --prometheus-threshold 0.01 --json
  ```
- 8 个新测试（聚合 avg/max/min/sum/p95/空值、range seam 成功/失败、
  range_mode 达标/违约投递/查询失败）

## 元数据
- `pyproject.toml` / `__init__.py` / SKILL.md / README → 3.9.0
- 导出 `_query_prometheus_range` / `_aggregate_range_values`
- 总测试 383 → 394（+3 工具结果 read +8 range 聚合 +1 版本净增 +2 其他调整）
- 3.9 / 3.11 / 3.12 全绿
