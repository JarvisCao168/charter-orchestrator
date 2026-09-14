# Feasibility Assessor

> **Skill ID / Skill 编号**: `analysis_02`
> **Category / 分类**: `analysis` — Analysis & Decision / 分析与决策
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 1 / 阶段一

---

## 职责 / Responsibility

**EN**: Assess technical, economic, and timeline feasibility of a requirement. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Feasibility Assessor under the Charter Orchestrator governance framework.

**中文**: 技术/经济/时间可行性评估。本 Skill 定义 FeasibilityAssessor 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "requirement_spec",
  "constraints"
]
```

## 输出 / Outputs

```json
[
  "feasibility_score",
  "risk_flags"
]
```

## 调用工具 / Tools Invoked

- `query_rule`
- `save_checkpoint`

## 治理约束 / Governance Constraints

- Token 预算 / Token Budget
- 治理规则查询 / Governance Rule Query

## 调用示例 / Usage

```
list_skills --category=analysis --id=analysis_02
```
