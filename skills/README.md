# Skills 工具箱 / Skills Toolbox（v1.0 文件化 skill 包 / file-based skill package）

47 个 Skill 定义，按 9 大类组织。每个 Skill 一个独立目录，内含 `SKILL.md`（输入/输出契约 + 调用工具 + 治理约束）。
47 Skill definitions organized into 9 categories. Each Skill has its own directory containing `SKILL.md` (I/O contract + tool invocations + governance constraints).

> **EN first / CN second** — 表格格式：`ID | 名称 | 目录` / Table format: `ID | name | directory`

---

## 环境与基础设施 / Environment & Infrastructure（7）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `env_01` | EnvironmentProbe | `skills/env/env_01/` |
| `env_02` | SandboxProvisioner | `skills/env/env_02/` |
| `env_03` | ModelRegistryProbe | `skills/env/env_03/` |
| `env_04` | GuardrailsBaseline | `skills/env/env_04/` |
| `env_05` | WorktreeProvisioner | `skills/env/env_05/` |
| `env_06` | TDDSetup | `skills/env/env_06/` |
| `env_07` | DependencyManager | `skills/env/env_07/` |

## 分析与决策 / Analysis & Decision（6）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `analysis_01` | CompetitorAnalyzer | `skills/analysis/analysis_01/` |
| `analysis_02` | FeasibilityAssessor | `skills/analysis/analysis_02/` |
| `analysis_03` | RiskAssessor | `skills/analysis/analysis_03/` |
| `analysis_04` | DistillationDecider | `skills/analysis/analysis_04/` |
| `analysis_05` | ArchitectureReviewer | `skills/analysis/analysis_05/` |
| `analysis_06` | CostOptimizer | `skills/analysis/analysis_06/` |

## 开发与工程 / Development & Engineering（12）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `dev_01` | CodeGenerator | `skills/dev/dev_01/` |
| `dev_02` | APIDesignPro | `skills/dev/dev_02/` |
| `dev_03` | FrontendEngineer | `skills/dev/dev_03/` |
| `dev_04` | DatabaseArchitect | `skills/dev/dev_04/` |
| `dev_05` | CodeReviewer | `skills/dev/dev_05/` |
| `dev_06` | SecurityAuditor | `skills/dev/dev_06/` |
| `dev_07` | PerformanceEngineer | `skills/dev/dev_07/` |
| `dev_08` | TDDEnforcer | `skills/dev/dev_08/` |
| `dev_09` | TechDebtTracker | `skills/dev/dev_09/` |
| `dev_10` | RefactoringAssistant | `skills/dev/dev_10/` |
| `dev_11` | SBOMGenerator | `skills/dev/dev_11/` |
| `dev_12` | BuildPipeline | `skills/dev/dev_12/` |

## 测试与验证 / Testing & Verification（5）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `test_01` | TestPlanner | `skills/test/test_01/` |
| `test_02` | TestExecutor | `skills/test/test_02/` |
| `test_03` | PerformanceBaseline | `skills/test/test_03/` |
| `test_04` | SecurityTest | `skills/test/test_04/` |
| `test_05` | AcceptanceValidator | `skills/test/test_05/` |

## 交付与运维 / Delivery & Operations（4）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `deploy_01` | ReleaseManager | `skills/deploy/deploy_01/` |
| `deploy_02` | SecurityAuditFinal | `skills/deploy/deploy_02/` |
| `deploy_03` | DeploymentOrchestrator | `skills/deploy/deploy_03/` |
| `deploy_04` | RollbackManager | `skills/deploy/deploy_04/` |

## 协作与记忆 / Collaboration & Memory（4）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `collab_01` | DropBoxManager | `skills/collab/collab_01/` |
| `collab_02` | TaskChainOrchestrator | `skills/collab/collab_02/` |
| `collab_03` | MeetingRecorder | `skills/collab/collab_03/` |
| `collab_04` | KnowledgeGraph | `skills/collab/collab_04/` |

## 工具与版本控制 / Tools & Version Control（4）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `tool_01` | GitWorkflow | `skills/tool/tool_01/` |
| `tool_02` | CI_CDPipeline | `skills/tool/tool_02/` |
| `tool_03` | VersionManager | `skills/tool/tool_03/` |
| `tool_04` | ConfigManager | `skills/tool/tool_04/` |

## 安全与治理 / Security & Governance（3）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `security_01` | GuardrailsEngine | `skills/security/security_01/` |
| `security_02` | AuditLogger | `skills/security/security_02/` |
| `security_03` | ComplianceChecker | `skills/security/security_03/` |

## 可观测性 / Observability（2）

| Skill ID | 名称 / Name | 目录 / Directory |
|----------|-------------|-------------------|
| `obs_01` | TraceCollector | `skills/obs/obs_01/` |
| `obs_02` | ObservabilityReport | `skills/obs/obs_02/` |

---

## 机器可读清单 / Machine-readable manifest

[`manifest.json`](manifest.json) — 47 条目，含每个 Skill 的名称、分类、调用工具、输入/输出契约。
47 entries with name, category, tools invoked, and I/O contracts.

## 一致性校验 / Consistency check

```bash
python scripts/validate_skills.py
```
校验 47 个文件齐全、引用的工具/规则均存在、manifest 与根 SKILL.md 一致。
Validates all 47 files present, tool/rule references valid, manifest consistent with root SKILL.md.
