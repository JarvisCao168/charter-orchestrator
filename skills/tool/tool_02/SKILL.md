# CI/CD Pipeline

> **Skill ID / Skill 编号**: `tool_02`
> **Category / 分类**: `tool` — Tools & Version Control / 工具与版本控制
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: 阶段六~八 / 阶段六~八

---

## 职责 / Responsibility

**EN**: CI/CD pipeline configuration and execution. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for CI/CD Pipeline under the Charter Orchestrator governance framework.

**中文**: CI/CD 流水线配置与执行。本 Skill 定义 CI_CDPipeline 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "ci_stages",
  "cd_policy"
]
```

## 输出 / Outputs

```json
[
  "pipeline",
  "deploy_hooks"
]
```

## 调用工具 / Tools Invoked

- `trigger_workflow`
- `execute_in_sandbox`

## 治理约束 / Governance Constraints

- 事件驱动 / Event-Driven
- 代码质量 / Code Quality

## 调用示例 / Usage

```
list_skills --category=tool --id=tool_02
```
