# Test Planner

> **Skill ID / Skill 编号**: `test_01`
> **Category / 分类**: `test` — Testing & Verification / 测试与验证
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 7 / 阶段七

---

## 职责 / Responsibility

**EN**: Create test plans and design test cases from feature specs. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Test Planner under the Charter Orchestrator governance framework.

**中文**: 测试计划制定与用例设计。本 Skill 定义 TestPlanner 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "feature_spec",
  "coverage_target"
]
```

## 输出 / Outputs

```json
[
  "test_plan",
  "test_cases"
]
```

## 调用工具 / Tools Invoked

- `query_rule`
- `save_checkpoint`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 治理规则查询 / Governance Rule Query

## 调用示例 / Usage

```
list_skills --category=test --id=test_01
```
