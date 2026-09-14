# Rollback Manager

> **Skill ID / Skill 编号**: `deploy_04`
> **Category / 分类**: `deploy` — Delivery & Operations / 交付与运维
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段八

---

## 职责 / Responsibility

**EN**: Rollback strategy design and execution. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Rollback Manager under the Charter Orchestrator governance framework.

**中文**: 回滚策略制定与执行。本 Skill 定义 RollbackManager 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "rollback_trigger",
  "last_good"
]
```

## 输出 / Outputs

```json
[
  "rollback_verdict",
  "restored_state"
]
```

## 调用工具 / Tools Invoked

- `restore_checkpoint`
- `manage_worktree`

## 治理约束 / Governance Constraints

- Checkpoint 状态管理 / Checkpoint State Management
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=deploy --id=deploy_04
```
