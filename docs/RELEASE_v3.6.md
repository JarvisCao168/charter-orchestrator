# v3.6.0 — MCP resources/subscriptions + SSE metrics 实时流 + demo-skill watch 接 OnCall gRPC

发布日期：2026-09-15

## ① MCP resources/subscribe + /mcp/sse?stream=metrics 实时推送（`charter/mcp_server.py`）

- `CharterMCPServer` 新增三个 JSON-RPC 方法（MCP resources 规范对齐）：
  - `resources/subscribe` — 按 client 记录订阅的 resource URI（线程安全 `set`）
  - `resources/unsubscribe` — 取消订阅
  - `resources/list_subscriptions` — 列出该 client 当前订阅
- 新增 `charter://metrics` 资源：Prometheus 格式的请求计数快照。
  - stdio 模式：返回静态说明（无 HTTP 计数器）
  - HTTP+SSE 模式：`_http_owner` 回读 `HTTPMCPServer._metrics_payload()`，暴露
    `charter_mcp_requests_total` / `charter_mcp_requests_by_endpoint_total` / `charter_mcp_uptime_seconds`
- `/mcp/sse?stream=metrics`：SSE 长连接，每 5s 推一帧 Prometheus 快照
  （多行 data 字段按 SSE 规范拆成多条 `data:` 行），供仪表盘实时刷新
- 5 个新测试（`tests/test_mcp_server.py`）

## ② demo-skill watch 接 OnCall gRPC（`charter/demo_skill.py`）

- 新增 `_deliver_oncall(alert, target, integration_name)`：把 watch SLO 告警
  通过 `charter.oncall_grpc_e2e.e2e_delivery_report` 真正投递到 Grafana OnCall。
  - `grpc` + 服务可用 → 真实 gRPC 投递，回写 receipt（request_id / ts）
  - 否则内置 `_MockChannel` 降级为 plan-only receipt（CI 无 OnCall 也绿）
- `run_watch(..., oncall_target, oncall_integration)`：每次 SLO 违约即调用
  投递，告警记录上挂 `oncall` 字段（delivered / plan_only / transport /
  target / request_id / receipt_ts）
- CLI：`--oncall-target grafana-oncall:50051 --oncall-integration pagerduty`
  ```bash
  make demo-skill SKILL=--watch --oncall-target grafana-oncall:50051
  python -m charter.demo_skill --watch --oncall-target localhost:50051 --json
  ```
- 4 个新测试（`tests/test_demo_skill.py`：plan-only 降级、breach 投递、
  SLO 达标不投递、模块不可用仍不崩）

## 元数据
- `pyproject.toml` / `__init__.py` / SKILL.md / README → 3.6.0；导出 `_deliver_oncall`
- 总测试 352 → 361（+5 MCP subscriptions +4 watch OnCall +1 版本净增）
- 3.9 / 3.11 / 3.12 全绿
