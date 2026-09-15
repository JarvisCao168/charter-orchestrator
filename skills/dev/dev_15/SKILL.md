# Bidir mTLS K8s Values

> **Skill ID / Skill 编号**: `dev_15`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段6
> **Module / 模块**: `charter.spire_k8s_mtls`

---

## 职责 / Responsibility

**EN**: Bidir mTLS K8s Values (SPIRE) — operationalizes `charter.spire_k8s_mtls` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Bidir mTLS K8s Values（SPIRE）。本 Skill 将 `charter.spire_k8s_mtls` 纳入治理框架，
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
- `query_trace`
- `guardrails`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_15
run_tool trace_operation --project_id=<pid>
```

