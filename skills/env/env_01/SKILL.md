# Environment Probe

> **Skill ID / Skill 编号**: `env_01`
> **Category / 分类**: `env` — Environment & Infrastructure / 环境与基础设施
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 0 / 阶段〇

---

## 职责 / Responsibility

**EN**: Detect host environment capabilities and available tooling. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Environment Probe under the Charter Orchestrator governance framework.

**中文**: 基础环境探测与能力发现。本 Skill 定义 EnvironmentProbe 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id"
]
```

## 输出 / Outputs

```json
[
  "env_report",
  "capability_matrix"
]
```

## 调用工具 / Tools Invoked

- `init_project`
- `query_status`

## 治理约束 / Governance Constraints

- 角色分工 / Role Assignment
- Token 预算 / Token Budget

## 调用示例 / Usage

```
list_skills --category=env --id=env_01
```
