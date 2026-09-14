# Guardrails Engine

> **Skill ID / Skill 编号**: `security_01`
> **Category / 分类**: `security` — Security & Governance / 安全与治理
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段全阶段 / 阶段全阶段

---

## 职责 / Responsibility

**EN**: Runtime security guardrails execution (input/output validation). This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Guardrails Engine under the Charter Orchestrator governance framework.

**中文**: 运行时安全护栏执行。本 Skill 定义 GuardrailsEngine 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "direction",
  "rule_set"
]
```

## 输出 / Outputs

```json
[
  "guard_result",
  "violations"
]
```

## 调用工具 / Tools Invoked

- `guardrails`
- `query_rule`

## 治理约束 / Governance Constraints

- Guardrails 安全护栏 / Guardrails Security
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=security --id=security_01
```
