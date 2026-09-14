# TDD Enforcer

> **Skill ID / Skill 编号**: `dev_08`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: On Each Commit / 每次提交
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Enforce red-green-refactor TDD cycle on every code commit. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for TDD Enforcer under the Charter Orchestrator governance framework.

**中文**: 强制红绿循环（Red→Green→Refactor）。本 Skill 定义 TDDEnforcer 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "module_path",
  "test_scope"
]
```

## 输出 / Outputs

```json
[
  "tdd_status",
  "coverage"
]
```

## 调用工具 / Tools Invoked

- `enforce_tdd`
- `manage_worktree`

## 治理约束 / Governance Constraints

- TDD 纪律 / TDD Discipline
- 代码质量 / Code Quality

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_08
```
