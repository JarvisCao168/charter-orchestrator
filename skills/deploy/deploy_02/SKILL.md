# Security Audit Final

> **Skill ID / Skill 编号**: `deploy_02`
> **Category / 分类**: `deploy` — Delivery & Operations / 交付与运维
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段八

---

## 职责 / Responsibility

**EN**: Pre-release final security audit and compliance gate. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Security Audit Final under the Charter Orchestrator governance framework.

**中文**: 发布前最终安全审计。本 Skill 定义 SecurityAuditFinal 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "release_candidate",
  "audit_scope"
]
```

## 输出 / Outputs

```json
[
  "final_audit",
  "blockers"
]
```

## 调用工具 / Tools Invoked

- `guardrails`
- `query_status`

## 治理约束 / Governance Constraints

- 安全红线 / Security Redline
- Guardrails 安全护栏 / Guardrails Security

## 调用示例 / Usage

```
list_skills --category=deploy --id=deploy_02
```
