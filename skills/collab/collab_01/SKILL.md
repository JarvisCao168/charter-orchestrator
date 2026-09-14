# Dropbox Manager

> **Skill ID / Skill 编号**: `collab_01`
> **Category / 分类**: `collab` — Collaboration & Memory / 协作与记忆
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段全阶段 / 阶段全阶段

---

## 职责 / Responsibility

**EN**: Asynchronous knowledge sharing and versioned document collaboration. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Dropbox Manager under the Charter Orchestrator governance framework.

**中文**: 异步知识共享与版本化文档协作。本 Skill 定义 DropBoxManager 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "doc_type",
  "participants"
]
```

## 输出 / Outputs

```json
[
  "dropbox_id",
  "shared_context"
]
```

## 调用工具 / Tools Invoked

- `create_dropbox`
- `query_status`

## 治理约束 / Governance Constraints

- 沟通规范 / Communication Protocol
- Checkpoint 状态管理 / Checkpoint State Management

## 调用示例 / Usage

```
list_skills --category=collab --id=collab_01
```
