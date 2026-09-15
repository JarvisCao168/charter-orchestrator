# Session Compression

> **Skill ID / Skill 编号**: `col_06`
> **Category / 分类**: `collab` — Collaboration & Memory / 协作与记忆
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 4 / 阶段4
> **Module / 模块**: `charter.memory_compress`

---

## 职责 / Responsibility

**EN**: Session Compression (Memory) — operationalizes `charter.memory_compress` under the Charter
Orchestrator governance framework. Defines the I/O contract, tool invocations,
and governance constraints for this capability.

**中文**: Session Compression（Memory）。本 Skill 将 `charter.memory_compress` 纳入治理框架，
定义其操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "agent_id",
  "query"
]
```

## 输出 / Outputs

```json
[
  "recalled_facts",
  "summary",
  "consensus_result"
]
```

## 调用工具 / Tools Invoked

- `save_checkpoint`
- `restore_checkpoint`
- `create_chat_chain`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- 权限边界 / Permission Boundary
- Token 预算 / Token Budget
- 审计追踪 / Audit Trail

## 调用示例 / Usage

```
list_skills --category=collab --id=col_06
run_tool save_checkpoint --project_id=<pid>
```

