# OnCall Delivery Payload/Route

> **Skill ID / Skill 编号**: `dev_18`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段6
> **Module / 模块**: `charter.oncall_deliver`

---

## 职责 / Responsibility

**EN**: OnCall Delivery Payload/Route (OnCall) — operationalizes `charter.oncall_deliver` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: OnCall Delivery Payload/Route（OnCall）。本 Skill 将 `charter.oncall_deliver` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "namespace"
]
```

## 输出 / Outputs

```json
[
  "k8s_values",
  "grpc_stubs",
  "iam_bundle"
]
```

## 调用工具 / Tools Invoked

- `trace_operation`
- `trigger_workflow`
- `create_dropbox`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_18
run_tool trace_operation --project_id=<pid>
```

