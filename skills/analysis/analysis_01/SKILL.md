# Competitor Analyzer

> **Skill ID / Skill 编号**: `analysis_01`
> **Category / 分类**: `analysis` — Analysis & Decision / 分析与决策
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 1 / 阶段一

---

## 职责 / Responsibility

**EN**: Analyze competitor features, architecture, and ecosystem. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Competitor Analyzer under the Charter Orchestrator governance framework.

**中文**: 竞品功能/架构/生态分析。本 Skill 定义 CompetitorAnalyzer 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "target_domain",
  "competitor_list"
]
```

## 输出 / Outputs

```json
[
  "feature_matrix",
  "architecture_notes"
]
```

## 调用工具 / Tools Invoked

- `query_status`
- `create_dropbox`

## 治理约束 / Governance Constraints

- 沟通规范 / Communication Protocol

## 调用示例 / Usage

```
list_skills --category=analysis --id=analysis_01
```
