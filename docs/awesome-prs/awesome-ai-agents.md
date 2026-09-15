# PR 草案：e2b-dev/awesome-ai-agents

> 提交方式：fork -> 新分支 -> 在 README 的 "Frameworks" 或 "Tools & Infrastructure"
> 分类下加入条目 -> 开 Pull Request。人工在 GitHub 完成（Contents token 无第三方仓库写权限）。

## 拟加入条目

### Charter Orchestrator — multi-agent governance & orchestration

- **Repo**: [JarvisCao168/charter-orchestrator](https://github.com/JarvisCao168/charter-orchestrator)
- **What**: Full-lifecycle governance & orchestration framework for AI agent teams.
  10-stage SOP, 13 governance rule categories, hard gates, TDD enforcement,
  guardrails, human-confirmation checkpoints — all as executable Python with
  260 CI-verified tests.
- **Unique**: the only framework in this list that ships *enforceable* governance
  (hard gates, not prompt suggestions) + production ops (OTel/Jaeger tracing,
  Prometheus/Mimir metrics, SPIFFE/SPIRE mTLS, OnCall gRPC, K8s judge pool,
  S3/IAM checkpointing).
- **MCP server**: `python -m charter.mcp_server` — 20 tools + 47 skill resources
  over stdio, mount in Claude Code / Codex / any MCP client.
- **Skill format**: Anthropic-compatible `SKILL.md` with YAML frontmatter.
- **Install**: `pip install charter-orchestrator`
- **License**: MIT · **Python**: 3.9-3.12

## PR 标题建议
"Add Charter Orchestrator — agent governance + orchestration framework"

## PR 正文建议
> Adding Charter Orchestrator: a governance & orchestration framework for agent
> teams that enforces 13 rule categories, 10-stage SOP, hard gates, TDD and
> guardrails in executable Python (not just prompts). Ships a stdio MCP server
> (20 tools + 47 skills), SPIFFE/mTLS identity, OTel/Prometheus observability,
> K8s judge pool, and S3/IAM checkpointing. MIT, Python 3.9-3.12, 260 CI tests.

