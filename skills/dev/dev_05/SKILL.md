# Code Reviewer

> **Skill ID / Skill 编号**: `dev_05`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Code quality review with improvement suggestions. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Code Reviewer under the Charter Orchestrator governance framework.

**中文**: 代码质量审查与改进建议。本 Skill 定义 CodeReviewer 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "diff_patch",
  "review_checklist"
]
```

## 输出 / Outputs

```json
[
  "review_comments",
  "approve_reject"
]
```

## 调用工具 / Tools Invoked

- `guardrails`
- `query_rule`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_05
```
