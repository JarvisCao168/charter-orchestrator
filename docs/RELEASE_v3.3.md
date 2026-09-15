# v3.3.0 — Per-Skill 单元测试 + demo-skill 一键跑通

发布日期：2026-09-15

## ① 60 个新 skill 补独立单元测试（`tests/test_v3_3_skills.py`，60 测试）

v3.2 的 MCP 测试只校验 107 个 skill 的路径/类别/工具引用，未逐个跑 module。
本版本为 v3.2 新增的 60 个 skill 每个补一个真实调用测试：

- 覆盖 55 个独立 charter 模块（judge / memory / oncall / spiffe / mTLS / IAM /
  PR diff / grafana / mimir / prometheus / trace 等）。
- 每个测试调用该 skill 对应模块的真实公开入口，断言返回结构正确。
- 离线安全：LLM 走 heuristic/None 路径，judge 无 api_key，OnCall 走 plan-only。
- 修了大量"测试用错签名"：init_project(project_name, project_type, objective)、
  HunkProposal(file, hunk_id, context, before, after, rationale)、
  PRSignals(pr_number)、vector_cross_merge 需 "centroid" 键、
  cluster_episodes 的 id 为 int、AttestationRequest 字段为 type/workload_data 等。

## ② make demo-skill 一键跑通真实模块链路（`charter/demo_skill.py` + `Makefile`）

- `make demo-skill SKILL=<id>` 解析 manifest -> 运行对应模块真实入口 -> 打印可读报告。
- 28 个 skill 有 bespoke 端到端 runner（6 类链路）：
  - obs_09/10/12：SLO breach → alert payload → OnCall gRPC e2e delivery report
  - dep_05/06/07/08：judge pool plan → cost autoscaler → K8s deploy bundle
  - col_05..col_10：session → compress → cluster → cross-language → vector merge
  - sec_01/02/03/06/07/08 + dev_15/16：X509 → SPIFFE SVID → bidir mTLS regression
  - tst_06/07/08：diff hunk → completion → cross-hunk → tree-sitter semantics
  - dev_19/20 + tst_10/11：team RBAC → IAM bundle → drift remediation
- 其余 79 个 skill 走 generic import + `__all__` introspection 回退（旧 47 个无
  module 字段的返回 manifest-driven 报告）。
- `make list-skill` 列出 28 个有 bespoke demo 的 skill。
- 9 个新测试（`tests/test_demo_skill.py`）覆盖：bespoke 全跑、generic 回退、
  未知 skill、`--list`/`--json`/退出码。

## 元数据
- `charter/__init__.py` 3.2.0 → 3.3.0；导出 `run_demo_skill` / `list_demo_skills` / `DEMO_SKILLS`
- `pyproject.toml` 3.2.0 → 3.3.0
- 总测试 260 → 334（+60 skill +9 demo-skill，-5 版本断言合并）
- 3.9 / 3.11 / 3.12 全绿
