# v3.8.0 — MCP 工具结果自动推送 + demo-skill watch --promql 模式

发布日期：2026-09-15

## ① MCP 工具结果变化自动推送（`charter/mcp_server.py`）

- `CharterMCPServer` 新增 `tools/subscribe_result` / `tools/unsubscribe_result` /
  `tools/list_result_subscriptions` JSON-RPC 方法：按 tool 名订阅结果变化。
- `tools/call` 执行后自动调用 `_notify_tool_result_changed(tool_name, outcome)`：
  向订阅该 tool 的所有 SSE client 推一条 `notifications/resources/updated` 事件
  （resource URI 为 `charter://tools/<name>/result`，payload 含 tool 名 + 完整结果）。
- `tools/subscribe_result` 同时记录在 `_tool_subscriptions` 和通用
  `_subscriptions` 中，保证 `notify_resource_changed` 的订阅门控正确放行。
- 4 个新测试（订阅往返 / 结果推送 / 未订阅不推 / 多客户端隔离）

## ② demo-skill watch `--promql` 模式：查线上 Prometheus（`charter/demo_skill.py`）

- 新增 `_query_prometheus(base_url, promql, _query=None)`：
  - 默认走 stdlib `urllib` GET `{base_url}/api/v1/query`
  - `_query` seam 可注入测试桩或带认证的传输层
  - 返回 `{"ok", "status", "data", "error"}`
- 新增 `run_watch_from_promql(base_url, promql, threshold_fn, iterations, ...)`：
  每轮向 Prometheus 发一条 PromQL 查询，由 `threshold_fn` 评估是否达标；
  不达标时通过 `_deliver_oncall` + `_deliver_alertmanager` 双通道投递告警。
  返回 watch 报告（history / alerts / slo_met / worst_observed）。
- CLI 新增 flag：
  ```bash
  python -m charter.demo_skill --promql 'error_rate:rate5m' \
      --prometheus-base http://localhost:9090 \
      --prometheus-threshold 0.01 \
      --iterations 5 --oncall-target grafana-oncall:50051 \
      --alertmanager-url http://am:9093/api/v2/alerts --json
  ```
- 7 个新测试（seam ok / seam 错 / seam 异常 / 达标不投 / 违约投递 /
  查询失败投 / CLI 缺 base 退出码 1）

## 元数据
- `pyproject.toml` / `__init__.py` / SKILL.md / README → 3.8.0
- 导出 `_query_prometheus` / `run_watch_from_promql`
- 总测试 372 → 388（+4 工具结果推送 +7 --promql +1 版本净增）
- 3.9 / 3.11 / 3.12 全绿
