# Multilingual Cluster Naming

> **Skill ID / Skill 编号**: `dev_13`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段6
> **Module / 模块**: `charter.cluster_multilingual`

---

## 职责 / Responsibility

**EN**: Multilingual Cluster Naming (i18n) — operationalizes `charter.cluster_multilingual` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Multilingual Cluster Naming（i18n）。本 Skill 将 `charter.cluster_multilingual` 纳入治理框架，
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

- `dispatch_to_model`
- `query_status`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_13
run_tool dispatch_to_model --project_id=<pid>
```

