# K8s SPIRE Node Socket Handshake

> **Skill ID / Skill 编号**: `sec_07`
> **Category / 分类**: `security` — Security & Governance / 安全与治理
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 5 / 阶段5
> **Module / 模块**: `charter.spire_node_handshake`

---

## 职责 / Responsibility

**EN**: K8s SPIRE Node Socket Handshake (SPIRE) — operationalizes `charter.spire_node_handshake` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: K8s SPIRE Node Socket Handshake（SPIRE）。本 Skill 将 `charter.spire_node_handshake` 纳入治理框架，
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
list_skills --category=security --id=sec_07
run_tool trace_operation --project_id=<pid>
```

