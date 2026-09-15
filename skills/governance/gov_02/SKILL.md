# CriticAgent (charter/critic_agent)

Global reflector: pre-checks a task plan, post-audits its outputs, and produces repair patches instead of just errors.

- `Critic.pre_check(plan)` - structural audit: dangling deps, cycles, duplicate produces, isolated steps.
- `Critic.post_audit(plan, outputs, rules)` - logical audit with pluggable rules.
- `Critic.reflect(plan, outputs)` - one-shot: pre + post + repairs folded into a `CriticReport`.

```python
from charter import Critic, CriticPlan, CriticStep
plan = CriticPlan(plan_id="p", steps=[CriticStep(id="a", produces=["x"]),
                                        CriticStep(id="b", depends_on=["a"])])
report = Critic().reflect(plan)
```