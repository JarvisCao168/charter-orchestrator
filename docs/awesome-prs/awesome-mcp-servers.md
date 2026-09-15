# PR 草案：punkpeye/awesome-mcp-servers

> 提交方式：fork 仓库 -> 新开分支 -> 把下面条目加入 README 的 "Server Implementations" 分类
> （Governance / Development 或 "Other" 分区），然后开 Pull Request。
> 注意：此 PR 由人工在 GitHub 网页/fork 完成（Contents token 无第三方仓库写权限）。

## 拟加入条目（Markdown，放入 README 的 MCP Servers 列表）

### Charter Orchestrator

- **Repo**: [JarvisCao168/charter-orchestrator](https://github.com/JarvisCao168/charter-orchestrator)
- **Description**: Full-lifecycle governance & orchestration framework for AI agents.
  Ships a stdio MCP server (`charter.mcp_server`) exposing 20 governance tools
  (stage gates, TDD enforcement, guardrails, model dispatch, checkpointing, tracing)
  and 47 structured skills as MCP resources. Mount it in Claude Code / Codex / any
  MCP client to run agent work under enforceable governance.
- **Transport**: stdio
- **Install**: `pip install charter-orchestrator[mcp]`
- **Run**: `python -m charter.mcp_server`
- **MCP config (Claude Desktop / Codex)**:

```json
{
  "charter-orchestrator": {
    "command": "python",
    "args": ["-m", "charter.mcp_server"]
  }
}
```

## PR 标题建议
"Add Charter Orchestrator (agent governance MCP server)"

## PR 正文建议
> Adding Charter Orchestrator — a governance/orchestration framework that ships a
> stdio MCP server with 20 enforceable governance tools and 47 structured skills.
> `pip install charter-orchestrator[mcp]` then `python -m charter.mcp_server`.
> MIT-licensed, Python 3.9-3.12, CI-tested.

