# Security Test

> **Skill ID / Skill 编号**: `test_04`
> **Category / 分类**: `test` — Testing & Verification / 测试与验证
> **Trigger / 触发方式**: Auto / 自动
> **Stage / 适用阶段**: Stage 7 / 阶段七

---

## 职责 / Responsibility

**EN**: Security testing: penetration, vulnerability scanning, and compliance verification. This skill defines the operational boundary, I/O contract, tool invocations, and governance constraints for Security Test under the Charter Orchestrator governance framework.

**中文**: 安全测试（渗透/漏洞/合规）。本 Skill 定义 SecurityTest 在治理规则下的具体操作边界、输入/输出契约、调用工具及关联治理规则。

## 输入 / Inputs

```json
[
  "attack_surface",
  "compliance_std"
]
```

## 输出 / Outputs

```json
[
  "findings",
  "pen_results"
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
list_skills --category=test --id=test_04
```
