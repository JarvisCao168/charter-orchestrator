# Performance Engineer

> **Skill ID / Skill 编号**: `dev_07`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Performance baseline establishment and optimization recommendations. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Performance Engineer under the Charter Orchestrator governance framework.

**中文**: 性能基线建立与优化建议。本 Skill 定义 PerformanceEngineer 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "benchmark_suite",
  "baseline"
]
```

## 输出 / Outputs

```json
[
  "perf_metrics",
  "bottlenecks"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `query_status`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- Token 预算 / Token Budget

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_07
```
