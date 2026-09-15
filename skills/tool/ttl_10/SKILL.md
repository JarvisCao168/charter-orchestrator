# Sandbox / Dropbox / Lifecycle

> **Skill ID / Skill 编号**: `ttl_10`
> **Category / 分类**: `tool` — Tools & Version Control / 工具与版本控制
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 5 / 阶段5
> **Module / 模块**: `charter.tools`

---

## 职责 / Responsibility

**EN**: Sandbox / Dropbox / Lifecycle (Tools) — operationalizes `charter.tools` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Sandbox / Dropbox / Lifecycle（Tools）。本 Skill 将 `charter.tools` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "template_spec"
]
```

## 输出 / Outputs

```json
[
  "rendered_template",
  "marketplace_entry",
  "checkpoint"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `create_dropbox`
- `manage_task_lifecycle`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=tool --id=ttl_10
run_tool execute_in_sandbox --project_id=<pid>
```

