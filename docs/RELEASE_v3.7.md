# v3.7.0 — MCP resources/changed 主动通知 + demo-skill watch 接 Alertmanager webhook

发布日期：2026-09-15

## ① MCP resources/changed 主动通知（`charter/mcp_server.py`）

- `CharterMCPServer` 新增 `notify_resource_changed(uri, client_key, payload)`：
  向订阅了该 resource 的 client 推一条 MCP `notifications/resources/updated` 事件。
- `HTTPMCPServer._inc_request` 计数后调用 `_broadcast_metrics_change()`，
  向所有订阅了 `charter://metrics` 的 SSE client 推一条带最新计数快照的通知。
- SSE metrics 流（`/mcp/sse?stream=metrics`）改为事件驱动：先推初始快照，
  之后阻塞在 per-client 队列上等 `resources/changed` push；收到后重发最新
  快照，30s keepalive 超时保持连接。
- 旧 5s 轮询循环（`_time.sleep(5)`）已移除，订阅指标变化事件取代轮询。
- `initialize` capabilities 升级为 `resources.subscribe: True`。
- 6 个新测试（订阅/未订阅/广播/单 client/取消订阅/事件驱动源码校验）

## ② demo-skill watch 接 Prometheus Alertmanager webhook（`charter/demo_skill.py`）

- 新增 `_deliver_alertmanager(alert, url, timeout_s, _post=None)`：
  - 构造 Alertmanager v4 格式 JSON payload（`alerts[]` + labels + annotations）
  - 通过 `_post` seam 注入测试桩或认证传输层；无 seam 时走 stdlib `urllib` POST
  - 网络 / 传输失败不崩 watch，降级为 plan-only receipt（`via=alertmanager-plan`）
- `run_watch(..., alertmanager_url, alertmanager_timeout_s)`：每次 SLO 违约时，
  在 OnCall 投递之外再发一条 Alertmanager webhook 投递；告警记录挂
  `alertmanager` 字段（`delivered`/`status`/`via`/`url`/`response_body` 或 `error`）
- CLI：`--alertmanager-url http://am:9093/api/v2/alerts --alertmanager-timeout 5`
  ```bash
  make demo-skill SKILL=--watch --alertmanager-url http://localhost:9093/api/v2/alerts
  python -m charter.demo_skill --watch --oncall-target grafana-oncall:50051 \
       --alertmanager-url http://am:9093/api/v2/alerts --json
  ```
- 5 个新测试（seam 成功/失败降级、run_watch 违约投递、SLO 达标不投递、
  seam 异常降级）

## 元数据
- `pyproject.toml` / `__init__.py` / SKILL.md / README → 3.7.0；导出 `_deliver_alertmanager`
- 总测试 361 → 372（+6 MCP 事件通知 +5 Alertmanager +1 版本净增）
- 3.9 / 3.11 / 3.12 全绿
