# v3.4.0 — demo-skill --all + MCP X-API-Key 鉴权

发布日期：2026-09-15

## ② demo-skill --all 一键跑全部 bespoke 链路（`charter/demo_skill.py`）

- 新增 `run_all_demos()`：遍历全部 6 类 bespoke 链路组（SLO→OnCall / Judge Pool /
  Memory 全链路 / mTLS+SPIFFE / PR diff / IAM+RBAC），按 runner 去重、逐个跑真实模块链路，
  失败不中断，返回汇总报告（`total_skills` / `passed` / `failed` / `chains` / `per_skill`）。
- 新增 `--all` CLI flag：`make demo-skill SKILL=... --all` 或
  `python -m charter.demo_skill --all`（可叠加 `--json`），打印人类可读汇总 + 退出码
  （全绿 0 / 有失败 1）。
- 7 个新测试（`tests/test_demo_skill.py`）。

## ③ MCP SSE/HTTP X-API-Key 鉴权（`charter/mcp_server.py`）

- `HTTPMCPServer` / `run_http_server` 新增 `api_key` 参数 + `CHARTER_MCP_API_KEY` 环境变量，
  网关所有 `/mcp/*` 端点（`/mcp/health` / `/mcp/tools` / `/mcp/sse` / `/mcp/message`）。
- 鉴权逻辑：未配置 key → 保持开放（向后兼容 v3.2）；配置 key → 请求需带匹配的
  `X-API-Key` header，否则 401。用 `hmac.compare_digest` 做常数时间比较防时序泄露。
- 启动：`CHARTER_MCP_API_KEY=... python -m charter.mcp_server`（stdio 不受影响）。
- 4 个新测试（`tests/test_mcp_server.py`）。

## 元数据
- `pyproject.toml` / `__init__.py` / SKILL.md / README → 3.4.0
- 导出 `run_all_demos`
- 总测试 334 → 348（+7 demo +4 auth +3 版本断言调整）
- 3.9 / 3.11 / 3.12 全绿
