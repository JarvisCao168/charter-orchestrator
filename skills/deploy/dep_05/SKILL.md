# Judge Pool K8s Plan

> **Skill ID / Skill 编号**: `dep_05`
> **Category / 分类**: `deploy` — Delivery & Operations / 交付与运维
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段8
> **Module / 模块**: `charter.judge_pool`

---

## 职责 / Responsibility

**EN**: Judge Pool K8s Plan (Judge) — operationalizes `charter.judge_pool` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Judge Pool K8s Plan（Judge）。本 Skill 将 `charter.judge_pool` 纳入治理框架，
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

- `dispatch_to_model`
- `trigger_workflow`
- `query_status`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=deploy --id=dep_05
run_tool dispatch_to_model --project_id=<pid>
```

