# Distillation Decider

> **Skill ID / Skill 编号**: `analysis_04`
> **Category / 分类**: `analysis` — Analysis & Decision / 分析与决策
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 3 / 阶段三

---

## 职责 / Responsibility

**EN**: Make open-source distillation decisions with compliance and complexity analysis. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Distillation Decider under the Charter Orchestrator governance framework.

**中文**: 开源蒸馏决策（含合规+复杂度+兼容性）。本 Skill 定义 DistillationDecider 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "component_candidates",
  "license"
]
```

## 输出 / Outputs

```json
[
  "distillation_decision",
  "compliance_report"
]
```

## 调用工具 / Tools Invoked

- `query_rule`
- `dispatch_to_model`

## 治理约束 / Governance Constraints

- 多模型调度 / Multi-Model Dispatch
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=analysis --id=analysis_04
```
