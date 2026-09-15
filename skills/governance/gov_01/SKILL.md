# ValidationGateway (charter/validation_gateway)

Three-layer validation gateway + circuit breaker for multi-Agent pipelines.

- **Layer 1 - schema**: `check_contract(output, schema)` enforces required fields + types.
- **Layer 2 - data alignment**: `check_data_alignment(output, upstream, key, rel_tol)` guards against the "500 billion -> 1200 billion" drift.
- **Layer 3 - consistency**: `check_consistency(conclusion, context, facts)` flags contradictions (growth vs decline).

`ValidationGateway.check_with_retry(producer)` retries locally then degrades (fills defaults) so the pipeline never crashes. `CircuitBreaker` tracks consecutive failures per tool and opens for a cooldown so a single bad tool cannot drag the chain down.

```python
from charter import ValidationGateway, CircuitBreaker
gw = ValidationGateway({"market_size": {"type": "float", "required": True}},
                     alignment_key="market_size")
out = gw.check_with_retry(lambda: {"market_size": 512e9},
                           upstream={"market_size": 500e9})
```