# API Design Pro

> **Skill ID / Skill 编号**: `dev_02`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Review and optimize RESTful/GraphQL API design. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for API Design Pro under the Charter Orchestrator governance framework.

**中文**: RESTful/GraphQL API 设计审查与优化。本 Skill 定义 APIDesignPro 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "api_endpoints",
  "data_model"
]
```

## 输出 / Outputs

```json
[
  "api_review",
  "optimization_hints"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `guardrails`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_02
```
