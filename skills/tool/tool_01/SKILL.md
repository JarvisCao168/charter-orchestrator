# Git Workflow

> **Skill ID / Skill 编号**: `tool_01`
> **Category / 分类**: `tool` — Tools & Version Control / 工具与版本控制
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段全阶段 / 阶段全阶段

---

## 职责 / Responsibility

**EN**: Git workflow management and branching strategy. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Git Workflow under the Charter Orchestrator governance framework.

**中文**: Git 工作流管理与分支策略。本 Skill 定义 GitWorkflow 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "branch_strategy",
  "repo"
]
```

## 输出 / Outputs

```json
[
  "branch_map",
  "workflow_rules"
]
```

## 调用工具 / Tools Invoked

- `manage_worktree`
- `execute_in_sandbox`

## 治理约束 / Governance Constraints

- 安全红线 / Security Redline
- 代码质量 / Code Quality

## 调用示例 / Usage

```
list_skills --category=tool --id=tool_01
```
