# Deployment Orchestrator

> **Skill ID / Skill 编号**: `deploy_03`
> **Category / 分类**: `deploy` — Delivery & Operations / 交付与运维
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段八

---

## 职责 / Responsibility

**EN**: Multi-environment deployment orchestration. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Deployment Orchestrator under the Charter Orchestrator governance framework.

**中文**: 多环境部署编排。本 Skill 定义 DeploymentOrchestrator 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "deploy_targets",
  "strategy"
]
```

## 输出 / Outputs

```json
[
  "deploy_report",
  "health_check"
]
```

## 调用工具 / Tools Invoked

- `trigger_workflow`
- `query_status`

## 治理约束 / Governance Constraints

- 事件驱动 / Event-Driven
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=deploy --id=deploy_03
```
