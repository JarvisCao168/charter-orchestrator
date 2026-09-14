# Model Registry Probe

> **Skill ID / Skill 编号**: `env_03`
> **Category / 分类**: `env` — Environment & Infrastructure / 环境与基础设施
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 0 / 阶段〇

---

## 职责 / Responsibility

**EN**: Discover available AI model runtimes and their health status. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Model Registry Probe under the Charter Orchestrator governance framework.

**中文**: 发现可用模型 Runtime。本 Skill 定义 ModelRegistryProbe 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "task_type",
  "complexity"
]
```

## 输出 / Outputs

```json
[
  "available_runtimes",
  "health_status"
]
```

## 调用工具 / Tools Invoked

- `dispatch_to_model`
- `query_rule`

## 治理约束 / Governance Constraints

- 多模型调度 / Multi-Model Dispatch

## 调用示例 / Usage

```
list_skills --category=env --id=env_03
```
