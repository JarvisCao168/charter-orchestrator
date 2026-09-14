# TDD Setup

> **Skill ID / Skill 编号**: `env_06`
> **Category / 分类**: `env` — Environment & Infrastructure / 环境与基础设施
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 5 / 阶段五

---

## 职责 / Responsibility

**EN**: Configure TDD test framework and enforce red-green-refactor cycle. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for TDD Setup under the Charter Orchestrator governance framework.

**中文**: 配置 TDD 测试框架。本 Skill 定义 TDDSetup 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "module_path",
  "test_framework"
]
```

## 输出 / Outputs

```json
[
  "tdd_configured",
  "test_dirs"
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
list_skills --category=env --id=env_06
```
