# Database Architect

> **Skill ID / Skill 编号**: `dev_04`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Schema optimization, indexing strategy, and query performance tuning. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Database Architect under the Charter Orchestrator governance framework.

**中文**: schema 优化、索引策略、查询性能。本 Skill 定义 DatabaseArchitect 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "schema_draft",
  "query_workload"
]
```

## 输出 / Outputs

```json
[
  "optimized_schema",
  "index_plan"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `query_status`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_04
```
