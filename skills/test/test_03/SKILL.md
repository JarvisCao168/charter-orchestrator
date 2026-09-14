# Performance Baseline

> **Skill ID / Skill 编号**: `test_03`
> **Category / 分类**: `test` — Testing & Verification / 测试与验证
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 7 / 阶段七

---

## 职责 / Responsibility

**EN**: Run performance benchmarks and regression analysis. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Performance Baseline under the Charter Orchestrator governance framework.

**中文**: 性能基准测试与对比分析。本 Skill 定义 PerformanceBaseline 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "perf_scenario",
  "threshold"
]
```

## 输出 / Outputs

```json
[
  "baseline",
  "regression_flags"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `query_status`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality

## 调用示例 / Usage

```
list_skills --category=test --id=test_03
```
