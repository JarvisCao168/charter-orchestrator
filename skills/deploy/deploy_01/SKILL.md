# Release Manager

> **Skill ID / Skill 编号**: `deploy_01`
> **Category / 分类**: `deploy` — Delivery & Operations / 交付与运维
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段八

---

## 职责 / Responsibility

**EN**: Version packaging and release management. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Release Manager under the Charter Orchestrator governance framework.

**中文**: 版本封装与发布管理。本 Skill 定义 ReleaseManager 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "version",
  "release_notes"
]
```

## 输出 / Outputs

```json
[
  "release_artifact",
  "version_tag"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `trigger_workflow`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 事件驱动 / Event-Driven

## 调用示例 / Usage

```
list_skills --category=deploy --id=deploy_01
```
