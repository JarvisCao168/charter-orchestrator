# Worktree Provisioner

> **Skill ID / Skill 编号**: `env_05`
> **Category / 分类**: `env` — Environment & Infrastructure / 环境与基础设施
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 5 / 阶段五

---

## 职责 / Responsibility

**EN**: Create isolated Git worktree environments for parallel development. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Worktree Provisioner under the Charter Orchestrator governance framework.

**中文**: 创建隔离开发环境。本 Skill 定义 WorktreeProvisioner 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "base_branch"
]
```

## 输出 / Outputs

```json
[
  "worktree_path",
  "branch_name"
]
```

## 调用工具 / Tools Invoked

- `manage_worktree`
- `init_project`

## 治理约束 / Governance Constraints

- 权限边界 / Permission Boundary
- Checkpoint 状态管理 / Checkpoint State Management

## 调用示例 / Usage

```
list_skills --category=env --id=env_05
```
