# Risk Assessor

> **Skill ID / Skill 编号**: `analysis_03`
> **Category / 分类**: `analysis` — Analysis & Decision / 分析与决策
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 1 / 阶段一

---

## 职责 / Responsibility

**EN**: Identify and register technical, security, and compliance risks. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Risk Assessor under the Charter Orchestrator governance framework.

**中文**: 技术风险/安全风险/合规风险评估。本 Skill 定义 RiskAssessor 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_scope",
  "threat_model"
]
```

## 输出 / Outputs

```json
[
  "risk_register",
  "mitigations"
]
```

## 调用工具 / Tools Invoked

- `query_rule`
- `save_checkpoint`

## 治理约束 / Governance Constraints

- 安全红线 / Security Redline
- Checkpoint 状态管理 / Checkpoint State Management

## 调用示例 / Usage

```
list_skills --category=analysis --id=analysis_03
```
