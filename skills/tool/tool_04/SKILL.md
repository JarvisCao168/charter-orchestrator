# Config Manager

> **Skill ID / Skill 编号**: `tool_04`
> **Category / 分类**: `tool` — Tools & Version Control / 工具与版本控制
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 0 / 阶段〇

---

## 职责 / Responsibility

**EN**: Project configuration management and environment switching. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Config Manager under the Charter Orchestrator governance framework.

**中文**: 项目配置管理与环境切换。本 Skill 定义 ConfigManager 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "env_profiles",
  "config_schema"
]
```

## 输出 / Outputs

```json
[
  "config_state",
  "env_switch"
]
```

## 调用工具 / Tools Invoked

- `init_project`
- `query_rule`

## 治理约束 / Governance Constraints

- 治理规则查询 / Governance Rule Query
- Token 预算 / Token Budget

## 调用示例 / Usage

```
list_skills --category=tool --id=tool_04
```
