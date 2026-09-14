# Architecture Reviewer

> **Skill ID / Skill 编号**: `analysis_05`
> **Category / 分类**: `analysis` — Analysis & Decision / 分析与决策
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 4 / 阶段四

---

## 职责 / Responsibility

**EN**: Automatically review architecture decisions and flag technical debt. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Architecture Reviewer under the Charter Orchestrator governance framework.

**中文**: 架构决策自动评审。本 Skill 定义 ArchitectureReviewer 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "architecture_doc",
  "design_decisions"
]
```

## 输出 / Outputs

```json
[
  "review_verdict",
  "tech_debt_flags"
]
```

## 调用工具 / Tools Invoked

- `guardrails`
- `query_rule`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 权限边界 / Permission Boundary

## 调用示例 / Usage

```
list_skills --category=analysis --id=analysis_05
```
