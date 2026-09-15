---
id: gov_06
name: gov_06_critic_plan
category: governance
description: Critic Plan Audit (closed-loop repair)
---

# Critic Plan Audit (closed-loop repair)

## What it does
Critic Plan Audit (closed-loop repair). Part of the v3.13 governance MCP toolset.

## MCP tool
Call via `charter://tools/gov/result` resource or `tools/call` with name `"gov"`.

## Python API
```python
from charter import model_router, critic_agent, semantic_trace, validation_gateway
# (see corresponding module for the public functions)
```

## Usage example
See `tests/test_gov_mcp_tools.py` and `docs/RELEASE_v3.13.md`.
