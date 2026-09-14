# Dependency Manager

> **Skill ID / Skill 编号**: `env_07`
> **Category / 分类**: `env` — Environment & Infrastructure / 环境与基础设施
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 5 / 阶段五

---

## 职责 / Responsibility

**EN**: Manage project dependencies and enforce version locking. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Dependency Manager under the Charter Orchestrator governance framework.

**中文**: 依赖管理与版本锁定。本 Skill 定义 DependencyManager 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "dependency_manifest",
  "version_constraints"
]
```

## 输出 / Outputs

```json
[
  "locked_versions",
  "conflicts"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `query_status`

## 治理约束 / Governance Constraints

- 代码质量 / Code Quality
- 安全红线 / Security Redline

## 调用示例 / Usage

```
list_skills --category=env --id=env_07
```
