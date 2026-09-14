# Compliance Checker

> **Skill ID / Skill 编号**: `security_03`
> **Category / 分类**: `security` — Security & Governance / 安全与治理
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 8 / 阶段八

---

## 职责 / Responsibility

**EN**: Compliance checks and report generation. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Compliance Checker under the Charter Orchestrator governance framework.

**中文**: 合规检查与报告生成。本 Skill 定义 ComplianceChecker 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "compliance_framework",
  "report_type"
]
```

## 输出 / Outputs

```json
[
  "compliance_report",
  "exceptions"
]
```

## 调用工具 / Tools Invoked

- `guardrails`
- `query_rule`

## 治理约束 / Governance Constraints

- Guardrails 安全护栏 / Guardrails Security
- 安全红线 / Security Redline
- 代码质量 / Code Quality

## 调用示例 / Usage

```
list_skills --category=security --id=security_03
```
