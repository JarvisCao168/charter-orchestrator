# Template PR Bot

> **Skill ID / Skill 编号**: `dep_09`
> **Category / 分类**: `deploy` — Delivery & Operations / 交付与运维
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段8
> **Module / 模块**: `charter.github_pr`

---

## 职责 / Responsibility

**EN**: Template PR Bot (PR) — operationalizes `charter.github_pr` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Template PR Bot（PR）。本 Skill 将 `charter.github_pr` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "pool_config"
]
```

## 输出 / Outputs

```json
[
  "deployment_plan",
  "s3_key",
  "health_probe"
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
list_skills --category=deploy --id=dep_09
run_tool manage_task_lifecycle --project_id=<pid>
```

