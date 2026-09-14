# SBOM Generator

> **Skill ID / Skill 编号**: `dev_11`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段八

---

## 职责 / Responsibility

**EN**: Generate Software Bill of Materials from build outputs. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for SBOM Generator under the Charter Orchestrator governance framework.

**中文**: 软件物料清单生成。本 Skill 定义 SBOMGenerator 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "build_output",
  "dependencies"
]
```

## 输出 / Outputs

```json
[
  "sbom_json",
  "license_inventory"
]
```

## 调用工具 / Tools Invoked

- `execute_in_sandbox`
- `query_status`

## 治理约束 / Governance Constraints

- 安全红线 / Security Redline
- 代码质量 / Code Quality

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_11
```
