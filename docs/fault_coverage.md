# Fault-Injection Coverage Matrix / 故障注入覆盖矩阵

Maps 14 fault seeds onto the 6 defense lines. Proven by
`charter.evaluation.FaultInjectionMatrix().report()` which asserts **full
coverage** (no seed is unguarded).

## 14 Fault Seeds / 14 类故障种子

| # | Fault / 故障 | Catches / 拦截防线 |
|---|---|---|
| 1 | ambiguous_delegation / 模糊委派 | dl1 需求澄清, dl3 人类审批 |
| 2 | missing_context / 上下文缺失 | dl1 |
| 3 | tool_fault / 工具故障 | dl5 TDD, dl6 发版自检 |
| 4 | schema_drift / 模式漂移 | dl6 |
| 5 | prompt_injection / 提示注入 | dl3, dl6 |
| 6 | budget_exhaustion / 预算耗尽 | dl6 |
| 7 | model_timeout / 模型超时 | dl6 |
| 8 | cascading_error / 级联错误 | dl2 文档固化, dl6 |
| 9 | stale_checkpoint / 陈旧快照 | dl2 |
| 10 | permission_escalation / 权限提升 | dl3 |
| 11 | secrets_leak / 密钥泄露 | dl6 |
| 12 | off_spec_code / 偏离规范 | dl5 |
| 13 | flaky_test / 不稳定测试 | dl5 |
| 14 | infinite_loop / 死循环 | dl6 |

## Defense Lines / 6 道防线

| ID | Defense / 防线 | Faults it catches / 拦截的故障 |
|---|---|---|
| dl1 | Requirement Clarification / 需求澄清 | #1, #2 |
| dl2 | Document Lock / 文档固化 | #8, #9 |
| dl3 | Human Approval / 人类审批 | #1, #5, #10 |
| dl4 | Branch Isolation / 分支隔离 | (isolation primitive - prevents parallel-state corruption) |
| dl5 | TDD Red-Green / TDD 红绿 | #3, #12, #13 |
| dl6 | Release Self-Check / 发版自检 | #3, #4, #5, #6, #7, #8, #11, #14 |

> **Note:** dl4 (branch isolation) is a structural control rather than a
> checker - it *prevents* state corruption across parallel agents instead of
> detecting a named fault. `FaultInjectionMatrix.report()` counts it under
> "utilization" but does not require it to catch a specific seed.

## How to extend / 如何扩展

Add a new fault seed and its defenses:

```python
from charter import FaultInjectionMatrix
fx = FaultInjectionMatrix()
fx.add_coverage("race_condition", ["dl4", "dl6"])
print(fx.report())
```
