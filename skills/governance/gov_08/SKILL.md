---
id: gov_08
name: gov_08_route_task
category: governance
description: Model Routing + Semantic Cache
---

# Model Routing + Semantic Cache

## What it does
Model Routing + Semantic Cache. Part of the v3.13 governance MCP toolset.

## MCP tool
Call via `charter://tools/gov/result` resource or `tools/call` with name `"gov"`.

## Python API
```python
from charter import model_router, critic_agent, semantic_trace, validation_gateway
# (see corresponding module for the public functions)
```

## Usage example
See `tests/test_gov_mcp_tools.py` and `docs/RELEASE_v3.13.md`.
