# Attestation Request/Verify

> **Skill ID / Skill 编号**: `sec_04`
> **Category / 分类**: `security` — Security & Governance / 安全与治理
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 5 / 阶段5
> **Module / 模块**: `charter.spiffe_attestation`

---

## 职责 / Responsibility

**EN**: Attestation Request/Verify (SPIFFE) — operationalizes `charter.spiffe_attestation` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Attestation Request/Verify（SPIFFE）。本 Skill 将 `charter.spiffe_attestation` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "trust_domain"
]
```

## 输出 / Outputs

```json
[
  "svid",
  "verification_report",
  "attestation_result"
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
list_skills --category=security --id=sec_04
run_tool trace_operation --project_id=<pid>
```

