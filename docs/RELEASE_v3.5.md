# v3.5.0 — demo-skill --watch SLO 告警 + MCP /metrics 端点

发布日期：2026-09-15

## ② demo-skill --watch 持续跑 + SLO 阈值告警（`charter/demo_skill.py`）

- 新增 `run_watch(iterations, slo_pct_threshold, as_json)`：持续跑全部 6 类 bespoke
  链路（`run_all_demos` 的每次迭代），按可用性 SLO 评估通过率，低于阈值即产生
  结构化告警（`severity` + `failed_skills` + `message`）。
- 新增 `_eval_slo(report, threshold)`：ratio vs 阈值，返回 met / alert。
- `--watch` CLI flag（可叠加 `--iterations` / `--slo-pct` / `--json`）：
  ```bash
  make demo-skill SKILL=--watch               # 默认 3 轮，SLO 90%
  python -m charter.demo_skill --watch --iterations 5 --slo-pct 95
  python -m charter.demo_skill --watch --json  # 机器可读（含 history/alerts/worst_ratio）
  ```
- SLO 语义：通过率（passed/total_skills）低于 `slo-pct` 即告警；severity 按
  ratio>=0.75 分 warning / critical。`--iterations=1` 为单发 watch。
- 7 个新测试（`tests/test_demo_skill.py`：_eval_slo met/breach、run_watch
  单轮/多轮/告警/worst_ratio、--watch 退出码 met/breach）。

## ③ MCP SSE/HTTP Prometheus /metrics 端点（`charter/mcp_server.py`）

- `HTTPMCPServer` 新增 `/metrics` 端点（Prometheus 文本格式，`text/plain; version=0.0.4`）：
  - `charter_mcp_requests_total{method, endpoint, status}` — 按方法/端点/状态类的请求计数
  - `charter_mcp_requests_by_endpoint_total{endpoint}` — 按端点计数
  - `charter_mcp_uptime_seconds` — 服务启动秒数
- 线程安全（`_metrics_lock` 保护计数），`_inc_request()` 在 do_GET/do_POST 各分支记录。
- **`/metrics` 无需 X-API-Key**（scrapers 可匿名抓），其余 `/mcp/*` 端点维持鉴权（v3.4）。
- 4 个新测试（`tests/test_mcp_server.py`：计数器自增 / by-endpoint / 状态类分桶 / 开放端点）。

## 元数据
- `pyproject.toml` / `__init__.py` / SKILL.md / README → 3.5.0；导出 `run_watch`
- 总测试 341 → 352（+7 watch +4 metrics +3 版本调整）
- 3.9 / 3.11 / 3.12 全绿
