# PR Sentiment Analysis

> **Skill ID / Skill 编号**: `col_12`
> **Category / 分类**: `collab` — Collaboration & Memory / 协作与记忆
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 4 / 阶段4
> **Module / 模块**: `charter.pr_sentiment`

---

## 职责 / Responsibility

**EN**: PR Sentiment Analysis (PR) — operationalizes `charter.pr_sentiment` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: PR Sentiment Analysis（PR）。本 Skill 将 `charter.pr_sentiment` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "agent_id",
  "query"
]
```

## 输出 / Outputs

```json
[
  "recalled_facts",
  "summary",
  "consensus_result"
]
```

## 调用工具 / Tools Invoked

- `manage_task_lifecycle`
- `trigger_workflow`
- `create_dropbox`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=collab --id=col_12
run_tool manage_task_lifecycle --project_id=<pid>
```

