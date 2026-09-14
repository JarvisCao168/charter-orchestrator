# Test Executor

> **Skill ID / Skill 编号**: `test_02`
> **Category / 分类**: `test` — Testing & Verification / 测试与验证
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 7 / 阶段七

---

## 职责 / Responsibility

**EN**: Execute automated test suites and analyze results. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Test Executor under the Charter Orchestrator governance framework.

**中文**: 自动化测试执行与结果分析。本 Skill 定义 TestExecutor 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "test_suite",
  "env"
]
```

## 输出 / Outputs

```json
[
  "results",
  "failures"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `query_status`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- TDD 纪律 / TDD Discipline

## 调用示例 / Usage

```
list_skills --category=test --id=test_02
```
