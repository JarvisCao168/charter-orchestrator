# Code Generator

> **Skill ID / Skill 编号**: `dev_01`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Generate code from requirements and design documents. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Code Generator under the Charter Orchestrator governance framework.

**中文**: 基于需求和设计生成代码。本 Skill 定义 CodeGenerator 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "module_spec",
  "design_doc"
]
```

## 输出 / Outputs

```json
[
  "generated_code",
  "test_stub"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `manage_worktree`
- `enforce_tdd`

## 治理约束 / Governance Constraints

- TDD 纪律 / TDD Discipline
- 代码质量 / Code Quality
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_01
```
