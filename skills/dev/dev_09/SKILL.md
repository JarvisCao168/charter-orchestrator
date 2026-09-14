# Tech Debt Tracker

> **Skill ID / Skill 编号**: `dev_09`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Identify, log, and prioritize technical debt items. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Tech Debt Tracker under the Charter Orchestrator governance framework.

**中文**: 技术债务识别与追踪。本 Skill 定义 TechDebtTracker 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "code_module",
  "debt_threshold"
]
```

## 输出 / Outputs

```json
[
  "debt_items",
  "priority"
]
```

## 调用工具 / Tools Invoked

- `query_status`
- `create_dropbox`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 沟通规范 / Communication Protocol

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_09
```
