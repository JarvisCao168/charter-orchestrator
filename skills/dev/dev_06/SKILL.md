# Security Auditor

> **Skill ID / Skill 编号**: `dev_06`
> **Category / 分类**: `dev` — Development & Engineering / 开发与工程
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 6 / 阶段六

---

## 职责 / Responsibility

**EN**: Code security scanning, dependency vulnerability detection, and compliance checks. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Security Auditor under the Charter Orchestrator governance framework.

**中文**: 代码安全扫描、依赖漏洞检测、合规检查。本 Skill 定义 SecurityAuditor 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "code_base",
  "dependency_list"
]
```

## 输出 / Outputs

```json
[
  "vulnerabilities",
  "security_score"
]
```

## 调用工具 / Tools Invoked

- `guardrails`
- `execute_in_sandbox`

## 治理约束 / Governance Constraints

- 安全红线 / Security Redline
- Guardrails 安全护栏 / Guardrails Security

## 调用示例 / Usage

```
list_skills --category=dev --id=dev_06
```
