# Version Manager

> **Skill ID / Skill 编号**: `tool_03`
> **Category / 分类**: `tool` — Tools & Version Control / 工具与版本控制
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段全阶段 / 阶段全阶段

---

## 职责 / Responsibility

**EN**: Semantic versioning management and changelog tracking. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Version Manager under the Charter Orchestrator governance framework.

**中文**: 语义化版本管理与变更追踪。本 Skill 定义 VersionManager 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "semver_policy",
  "changelog"
]
```

## 输出 / Outputs

```json
[
  "version_matrix",
  "migration_notes"
]
```

## 调用工具 / Tools Invoked

- `query_status`
- `manage_task_lifecycle`

## 治理约束 / Governance Constraints

- 沟通规范 / Communication Protocol
- Checkpoint 状态管理 / Checkpoint State Management

## 调用示例 / Usage

```
list_skills --category=tool --id=tool_03
```
