# PR 草案：hesreallyhim/awesome-claude-code

> 提交方式：fork -> 新分支 -> 在 README 的 "Skills" 或 "Frameworks / Tools" 分类下
> 加入条目 -> 开 Pull Request。人工在 GitHub 完成（Contents token 无第三方仓库写权限）。

## 拟加入条目

### Charter Orchestrator — agent governance framework

- **Repo**: [JarvisCao168/charter-orchestrator](https://github.com/JarvisCao168/charter-orchestrator)
- **What**: Full-lifecycle governance & orchestration framework for AI coding agents.
  10-stage SOP, 13 rule categories, hard gates, TDD enforcement, guardrails, and
  human-confirmation points — all executable Python (not just prompt text).
- **Skill format**: ships Anthropic-compatible `SKILL.md` (YAML frontmatter +
  `allowed-tools` + `charter-tools`/`charter-skills`), so Claude Code discovers it
  natively. 47 structured skills across 9 categories (env/dev/test/deploy/security/obs...).
- **MCP**: stdio MCP server (`python -m charter.mcp_server`) exposing 20 tools +
  47 skill resources — mount in Claude Code / Codex.
- **Install**: `pip install charter-orchestrator`
- **License**: MIT · **Python**: 3.9-3.12 · **CI**: green on 3 versions

## PR 标题建议
"Add Charter Orchestrator — governance framework + skills + MCP server"

## PR 正文建议
> Adding Charter Orchestrator: an agent governance & orchestration framework with
> Anthropic-compatible SKILL.md (47 skills, 20 tools, 10-stage SOP, 13 rule
> categories, hard gates + TDD + guardrails) and a stdio MCP server for
> Claude Code / Codex. MIT, Python 3.9-3.12, CI-tested.

