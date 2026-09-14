# Observability Report

> **Skill ID / Skill 编号**: `obs_02`
> **Category / 分类**: `obs` — Observability / 可观测性
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 9 / 阶段九

---

## 职责 / Responsibility

**EN**: Observability report generation and metrics analysis. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Observability Report under the Charter Orchestrator governance framework.

**中文**: 可观测性报告生成与指标分析。本 Skill 定义 ObservabilityReport 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "time_range",
  "kpi_set"
]
```

## 输出 / Outputs

```json
[
  "observability_report",
  "anomalies"
]
```

## 调用工具 / Tools Invoked

- `query_trace`
- `query_status`

## 治理约束 / Governance Constraints

- Checkpoint 状态管理 / Checkpoint State Management
- 沟通规范 / Communication Protocol

## 调用示例 / Usage

```
list_skills --category=obs --id=obs_02
```
