# Trace Link & Jaeger Query

> **Skill ID / Skill 编号**: `obs_04`
> **Category / 分类**: `obs` — Observability / 可观测性
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 7 / 阶段7
> **Module / 模块**: `charter.trace_link`

---

## 职责 / Responsibility

**EN**: Trace Link & Jaeger Query (OTel) — operationalizes `charter.trace_link` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Trace Link & Jaeger Query（OTel）。本 Skill 将 `charter.trace_link` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "metrics"
]
```

## 输出 / Outputs

```json
[
  "trace_report",
  "alert_payload",
  "slo_summary"
]
```

## 调用工具 / Tools Invoked

- `trace_operation`
- `query_trace`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=obs --id=obs_04
run_tool trace_operation --project_id=<pid>
```

