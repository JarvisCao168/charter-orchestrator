# SemanticTrace (charter/semantic_trace)

Full-link semantic tracing: records the input->output embedding similarity of every tool/agent call and flags hallucinations when the output drifts too far from the input.

- `SemanticTracer` - accumulates semantic spans; `record` computes cosine similarity, `guard` intercepts hallucinations.
- `cosine_similarity(a, b)` - stdlib vector math.

```python
from charter import SemanticTracer
tracer = SemanticTracer(threshold=0.2)
s = tracer.record("t", "query stock price", "lorem ipsum")
assert s.verdict == "hallucination"
```