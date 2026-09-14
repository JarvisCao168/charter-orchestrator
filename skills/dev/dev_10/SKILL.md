# Refactoring Assistant

> **Skill ID / Skill 编号**: `dev_10`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Code refactoring assistance with risk assessment. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Refactoring Assistant under the Charter Orchestrator governance framework.

**中文**: 代码重构辅助与风险评估。本 Skill 定义 RefactoringAssistant 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "target_code",
  "refactor_intent"
]
```

## 输出 / Outputs

```json
[
  "refactored_code",
  "risk_assessment"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `enforce_tdd`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- TDD 纪律 / TDD Discipline

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_10
```
