# Judge Weighted Voting

> **Skill ID / Skill 编号**: `ana_08`
> **Category / 分类**: `analysis` — Analysis & Decision / 分析与决策
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 1 / 阶段1
> **Module / 模块**: `charter.judge_voting`

---

## 职责 / Responsibility

**EN**: Judge Weighted Voting (Judge) — operationalizes `charter.judge_voting` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Judge Weighted Voting（Judge）。本 Skill 将 `charter.judge_voting` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "artifacts"
]
```

## 输出 / Outputs

```json
[
  "judge_scores",
  "embedding",
  "cluster_report"
]
```

## 调用工具 / Tools Invoked

- `dispatch_to_model`
- `trigger_workflow`
- `query_status`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=analysis --id=ana_08
run_tool dispatch_to_model --project_id=<pid>
```

