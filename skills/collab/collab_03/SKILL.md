# Meeting Recorder

> **Skill ID / Skill 编号**: `collab_03`
> **Category / 分类**: `collab` — Collaboration & Memory / 协作与记忆
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段全阶段 / 阶段全阶段

---

## 职责 / Responsibility

**EN**: Meeting minutes and decision log recording. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Meeting Recorder under the Charter Orchestrator governance framework.

**中文**: 会议纪要与决策记录。本 Skill 定义 MeetingRecorder 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "meeting_type",
  "attendees"
]
```

## 输出 / Outputs

```json
[
  "minutes",
  "decision_log"
]
```

## 调用工具 / Tools Invoked

- `create_dropbox`
- `create_chat_chain`

## 治理约束 / Governance Constraints

- 沟通规范 / Communication Protocol

## 调用示例 / Usage

```
list_skills --category=collab --id=collab_03
```
