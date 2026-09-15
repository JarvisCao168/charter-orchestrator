# ModelRouter + SemanticCache (charter/model_router)

Cost control: route cheap tasks to a small model, reserve the expensive model for complex tasks, and cache results so identical requests don't re-burn tokens.

- `TaskProfile.complexity()` - 0..100 score from depth / fan-in / risk / tokens / reasoning.
- `ModelRouter` - picks the cheapest tier that satisfies the complexity floor.
- `SemanticCache` - bounded LRU keyed by a semantic hash; hit-rate stats.

```python
from charter import TaskProfile, ModelRouter, SemanticCache
r = ModelRouter().route(TaskProfile(depth=10, risk=0.9, tokens=4096))
assert r["tier"] == "large"
```