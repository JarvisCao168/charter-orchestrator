# Audit Logger

> **Skill ID / Skill 编号**: `security_02`
> **Category / 分类**: `security` — Security & Governance / 安全与治理
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段全阶段 / 阶段全阶段

---

## 职责 / Responsibility

**EN**: Operation audit log recording and tamper-evident management. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Audit Logger under the Charter Orchestrator governance framework.

**中文**: 操作审计日志记录与管理。本 Skill 定义 AuditLogger 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "event_stream",
  "retention"
]
```

## 输出 / Outputs

```json
[
  "audit_log",
  "tamper_check"
]
```

## 调用工具 / Tools Invoked

- `trace_operation`
- `query_trace`

## 治理约束 / Governance Constraints

- Checkpoint 状态管理 / Checkpoint State Management
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=security --id=security_02
```
