# v3.1.0 — MCP 封装 + 官方 SKILL.md 格式 + 生态收录

发布日期：2026-09-15

## 新增

### P0：MCP Server（`charter/mcp_server.py`）
- 20 个治理工具 + 47 个 skill 以 stdio MCP server 暴露，JSON-RPC 2.0（MCP 2024-11-05 兼容）
- 无外部 MCP SDK 依赖（纯 stdlib JSON-RPC over stdio）
- 支持方法：`initialize` / `tools/list` / `tools/call` / `resources/list` / `resources/read` / `ping`
- 运行：`python -m charter.mcp_server`
- 挂载（Claude Code / Codex / `.mcp.json`）：
  ```json
  { "mcpServers": { "charter-orchestrator": { "command": "python", "args": ["-m","charter.mcp_server"] } } }
  ```
- 27 个新测试（`tests/test_mcp_server.py`）

### P0：Awesome List 收录草案（`docs/awesome-prs/`）
- 3 份 PR 草案：punkpeye/awesome-mcp-servers、hesreallyhim/awesome-claude-code、e2b-dev/awesome-ai-agents
- 含拟加入条目、PR 标题、PR 正文（需人工 fork 提交，Contents token 无第三方仓库写权限）

### P1：SKILL.md 对齐 Anthropic 官方格式
- 顶部加 YAML frontmatter：`name` / `description`（含 Use when）/ `version` / `license` / `tags`
  / `allowed-tools`（20）/ `charter-tools`（20）/ `charter-skills`（47，按 9 类）/ `mcp-server`
- 正文（10 阶段 SOP / 47 skill / 13 类规则 / 双语）全部保留

### 依赖与元数据
- `pyproject.toml`：version 3.0.0 -> 3.1.0；新增 `[mcp]` extra（`mcp` 可选包）
- `charter/__init__.py`：`__version__` -> 3.1.0；导出 `CharterMCPServer` / `list_mcp_tools` / `load_skill` / `run_tool`

## 测试
- 260 个测试（原 233 + 27 MCP），3.9 / 3.11 / 3.12 全绿

## 修复
- 修正上一轮 `pyproject.toml` 双引号语法错误遗留（version 行）
- `init_project` / `confirm_gate` / `enforce_tdd` 的 MCP 调用签名与核心 API 对齐
