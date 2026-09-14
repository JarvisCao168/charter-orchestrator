# Trace Collector

> **Skill ID / Skill 编号**: `obs_01`
> **Category / 分类**: `obs` — Observability / 可观测性
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段全阶段 / 阶段全阶段

---

## 职责 / Responsibility

**EN**: Trace/Span data collection and aggregation. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Trace Collector under the Charter Orchestrator governance framework.

**中文**: Trace/Span 数据收集与聚合。本 Skill 定义 TraceCollector 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "span_root",
  "sampling"
]
```

## 输出 / Outputs

```json
[
  "trace_tree",
  "metrics"
]
```

## 调用工具 / Tools Invoked

- `trace_operation`
- `query_trace`

## 治理约束 / Governance Constraints

- Checkpoint 状态管理 / Checkpoint State Management

## 调用示例 / Usage

```
list_skills --category=obs --id=obs_01
```
