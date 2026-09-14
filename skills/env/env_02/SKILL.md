# Sandbox Provisioner

> **Skill ID / Skill 编号**: `env_02`
> **Category / 分类**: `env` — Environment & Infrastructure / 环境与基础设施
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 0 / 阶段〇

---

## 职责 / Responsibility

**EN**: Provision isolated sandbox environments for safe code execution. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Sandbox Provisioner under the Charter Orchestrator governance framework.

**中文**: 沙箱环境快速搭建。本 Skill 定义 SandboxProvisioner 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "project_id",
  "sandbox_type"
]
```

## 输出 / Outputs

```json
[
  "sandbox_id",
  "isolation_level"
]
```

## 调用工具 / Tools Invoked

- `init_project`
- `execute_in_sandbox`

## 治理约束 / Governance Constraints

- 安全红线 / Security Redline
- 权限边界 / Permission Boundary

## 调用示例 / Usage

```
list_skills --category=env --id=env_02
```
