# PR Diff Tree-Sitter Semantics

> **Skill ID / Skill 编号**: `tst_08`
> **Category / 分类**: `test` — Testing & Verification / 测试与验证
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 7 / 阶段7
> **Module / 模块**: `charter.pr_diff_semantics`

---

## 职责 / Responsibility

**EN**: PR Diff Tree-Sitter Semantics (PR) — operationalizes `charter.pr_diff_semantics` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: PR Diff Tree-Sitter Semantics（PR）。本 Skill 将 `charter.pr_diff_semantics` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "diff_hunks"
]
```

## 输出 / Outputs

```json
[
  "consistency_report",
  "suggestions",
  "iam_policy"
]
```

## 调用工具 / Tools Invoked

- `enforce_tdd`
- `execute_in_sandbox`
- `guardrails`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=test --id=tst_08
run_tool enforce_tdd --project_id=<pid>
```

