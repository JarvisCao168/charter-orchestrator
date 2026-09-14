# Quick Start / 快速上手

> Charter Orchestrator v1.1.0 - **executable**, not just a spec.
> 从"读文档"到"跑起来"只需 5 分钟。

## 1. Install / 安装

```bash
git clone https://github.com/JarvisCao168/charter-orchestrator.git
cd charter-orchestrator
pip install -e .            # installs the `charter` package + CLI
```

Requires Python 3.9+. No external deps for the core (SQLite ships with Python).

## 2. Run the governed demo / 跑通治理演示

```bash
python -m charter.cli demo
```

You will see: 10-stage SOP advance, gate enforcement, **TDD violation blocked**,
**secret leak caught by guardrail**, checkpoint save/restore, LLM-judge evaluation,
and the 14-fault coverage report. Every layer runs for real.

## 3. Use it in your own code / 在自己的代码里用

```python
from charter import (init_project, advance_stage, confirm_gate,
                     query_status, enforce_tdd, evaluate_agent)

pid = init_project("my-feature", "software_dev", "add SSO login")["project_id"]

ev = {"env_report": True, "problem_statement": "...", "feasibility_score": 0.9,
      "acceptance_criteria": "user logs in via SSO", "requirement_signoff": True,
      "distillation_decision": "new", "reference_list": ["oauth2"],
      "architecture_doc_locked": True, "tech_selection": "python",
      "env_ready": True, "ci_green": True, "worktree_isolated": True,
      "code_review_passed": True, "tdd_red_green": True,
      "tests_written": True, "coverage": 0.85}

for stage in ["stage_1", "stage_2", "stage_3", "stage_4"]:
    advance_stage(pid, stage, evidence=ev)
    confirm_gate(pid, f"gate_{stage}", "hybrid", ev, reviewer_id="you")

status = query_status(pid, detail_level="full")
print(status["current_stage"], status["gates_passed"])

# P0: continuous evaluation
score = evaluate_agent(pid, {"test_coverage": 0.85, "tests_written": True,
                             "violations": [], "token_ratio": 0.4})
print(score.verdict, score.weighted)
```

## 4. The governance primitives / 治理原语

| Primitive / 原语 | What it enforces / 强制什么 |
|---|---|
| `advance_stage` | 10-stage SOP, no backward jumps |
| `confirm_gate` | 6 defense lines + per-stage checks |
| `enforce_tdd` | red-green-refactor (off / soft / strict) |
| `guardrails` | secret/destructive-pattern filter |
| `save/restore_checkpoint` | state snapshot & rollback |
| `evaluate_agent` | LLM-as-judge quality gate |
| `memory_recall` | cross-session agent memory |
| `FaultInjectionMatrix` | 14-fault defense coverage proof |

## 5. Verify integrity / 校验完整性

```bash
python scripts/validate_skills.py   # 20 tools, 47 skills, manifest, core
python -m pytest tests/            # 10 executable tests
```

## 6. CLI reference / 命令行

```
charter demo            # run the full governed demo
python -m charter       # same as above
```

---
## 故障注入矩阵 / Fault-Injection Matrix

`charter.evaluation.FaultInjectionMatrix` maps 14 fault seeds (MAST/OrchestraBench
inspired) onto the 6 defense lines and reports coverage. Run it:

```python
from charter import FaultInjectionMatrix
print(FaultInjectionMatrix().report())
# {fault_seeds: 14, status: "full", uncovered: [], defense_utilization: {...}}
```

See `docs/fault_coverage.md` for the full mapping.
