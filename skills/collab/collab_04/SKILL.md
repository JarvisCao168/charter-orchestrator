# Knowledge Graph

> **Skill ID / Skill 编号**: `collab_04`
> **Category / 分类**: `collab` — Collaboration & Memory / 协作与记忆
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 9 / 阶段九

---

## 职责 / Responsibility

**EN**: Project knowledge graph construction and querying. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Knowledge Graph under the Charter Orchestrator governance framework.

**中文**: 项目知识图谱构建与更新。本 Skill 定义 KnowledgeGraph 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_entities",
  "relations"
]
```

## 输出 / Outputs

```json
[
  "knowledge_graph",
  "query_index"
]
```

## 调用工具 / Tools Invoked

- `query_status`
- `create_dropbox`

## 治理约束 / Governance Constraints

- Checkpoint 状态管理 / Checkpoint State Management
- 沟通规范 / Communication Protocol

## 调用示例 / Usage

```
list_skills --category=collab --id=collab_04
```
