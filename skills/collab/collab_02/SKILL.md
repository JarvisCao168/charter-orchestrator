# Task Chain Orchestrator

> **Skill ID / Skill 编号**: `collab_02`
> **Category / 分类**: `collab` — Collaboration & Memory / 协作与记忆
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段全阶段 / 阶段全阶段

---

## 职责 / Responsibility

**EN**: Atomic task chain generation and execution orchestration. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Task Chain Orchestrator under the Charter Orchestrator governance framework.

**中文**: 原子任务链生成与执行编排。本 Skill 定义 TaskChainOrchestrator 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "objective",
  "task_graph"
]
```

## 输出 / Outputs

```json
[
  "chain_status",
  "blockers"
]
```

## 调用工具 / Tools Invoked

- `create_chat_chain`
- `manage_task_lifecycle`

## 治理约束 / Governance Constraints

- 沟通规范 / Communication Protocol
- 事件驱动 / Event-Driven

## 调用示例 / Usage

```
list_skills --category=collab --id=collab_02
```
