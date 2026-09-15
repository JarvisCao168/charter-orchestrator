# Checkpoint IAM Drift Remediate

> **Skill ID / Skill 编号**: `tst_11`
> **Category / 分类**: `test` — Testing & Verification / 测试与验证
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 7 / 阶段7
> **Module / 模块**: `charter.checkpoint_iam_remediate`

---

## 职责 / Responsibility

**EN**: Checkpoint IAM Drift Remediate (IAM) — operationalizes `charter.checkpoint_iam_remediate` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Checkpoint IAM Drift Remediate（IAM）。本 Skill 将 `charter.checkpoint_iam_remediate` 纳入治理框架，
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

- `guardrails`
- `execute_in_sandbox`
- `query_rule`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=test --id=tst_11
run_tool guardrails --project_id=<pid>
```

