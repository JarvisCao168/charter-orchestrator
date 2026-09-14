# Build Pipeline

> **Skill ID / Skill 编号**: `dev_12`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段八

---

## 职责 / Responsibility

**EN**: Configure and execute CI/CD build pipelines. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Build Pipeline under the Charter Orchestrator governance framework.

**中文**: 构建流水线配置与执行。本 Skill 定义 BuildPipeline 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "pipeline_spec",
  "triggers"
]
```

## 输出 / Outputs

```json
[
  "pipeline_config",
  "ci_status"
]
```

## 调用工具 / Tools Invoked

- `trigger_workflow`
- `execute_in_sandbox`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 事件驱动 / Event-Driven

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_12
```
