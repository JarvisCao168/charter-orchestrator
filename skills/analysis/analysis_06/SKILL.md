# Cost Optimizer

> **Skill ID / Skill 编号**: `analysis_06`
> **Category / 分类**: `analysis` — Analysis & Decision / 分析与决策
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 3 / 阶段三

---

## 职责 / Responsibility

**EN**: Evaluate and optimize AI model costs per task profile. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Cost Optimizer under the Charter Orchestrator governance framework.

**中文**: 模型成本评估与优化建议。本 Skill 定义 CostOptimizer 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "task_profile",
  "budget_tier"
]
```

## 输出 / Outputs

```json
[
  "cost_estimate",
  "recommended_model"
]
```

## 调用工具 / Tools Invoked

- `dispatch_to_model`
- `query_status`

## 治理约束 / Governance Constraints

- 多模型调度 / Multi-Model Dispatch
- Token 预算 / Token Budget

## 调用示例 / Usage

```
list_skills --category=analysis --id=analysis_06
```
