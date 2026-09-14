# Guardrails Baseline

> **Skill ID / Skill 编号**: `env_04`
> **Category / 分类**: `env` — Environment & Infrastructure / 环境与基础设施
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 0 / 阶段〇

---

## 职责 / Responsibility

**EN**: Configure project-level security guardrails baseline rules. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Guardrails Baseline under the Charter Orchestrator governance framework.

**中文**: 配置项目级安全护栏基线。本 Skill 定义 GuardrailsBaseline 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "rule_set"
]
```

## 输出 / Outputs

```json
[
  "baseline_config",
  "violation_policy"
]
```

## 调用工具 / Tools Invoked

- `guardrails`
- `init_project`

## 治理约束 / Governance Constraints

- Guardrails 安全护栏 / Guardrails Security
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=env --id=env_04
```
