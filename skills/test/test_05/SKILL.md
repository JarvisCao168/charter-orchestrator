# Acceptance Validator

> **Skill ID / Skill 编号**: `test_05`
> **Category / 分类**: `test` — Testing & Verification / 测试与验证
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 7 / 阶段七

---

## 职责 / Responsibility

**EN**: Validate deliverables against acceptance criteria and sign off. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Acceptance Validator under the Charter Orchestrator governance framework.

**中文**: 验收标准验证与确认。本 Skill 定义 AcceptanceValidator 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "acceptance_criteria",
  "test_evidence"
]
```

## 输出 / Outputs

```json
[
  "acceptance_verdict",
  "signoff"
]
```

## 调用工具 / Tools Invoked

- `confirm_gate`
- `query_rule`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 沟通规范 / Communication Protocol

## 调用示例 / Usage

```
list_skills --category=test --id=test_05
```
