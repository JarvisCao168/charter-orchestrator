"""v3.13: governance tools exposed via the MCP surface.

Covers the 4 new tools (validate_output / critic_plan / trace_span / route_task):
- TOOL_DEFINITIONS now lists 24 tools
- run_tool dispatches each gov tool to the right module
- unknown tools still return an error envelope
- SemanticCache remote mirror is wired through route_task(use_cache=True)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from charter.mcp_server import list_mcp_tools, run_tool


def test_tool_count_is_24():
    tools = list_mcp_tools()
    assert len(tools) == 24, f"expected 24 tools, got {len(tools)}"
    names = {t["name"] for t in tools}
    for t in ("validate_output", "critic_plan", "trace_span", "route_task"):
        assert t in names, f"gov tool {t} missing from MCP surface"


def test_validate_output_pass():
    r = run_tool("validate_output", {
        "payload": {"market_size": 512e9, "source": "research"},
        "contract": {"market_size": {"type": "float", "required": True},
                     "source": {"type": "str", "required": True}},
    })
    assert r["ok"], r
    assert r["result"]["passed"] is True


def test_validate_output_alignment_fail():
    r = run_tool("validate_output", {
        "payload": {"market_size": 999e9, "source": "research"},
        "contract": {"market_size": {"type": "float", "required": True},
                     "source": {"type": "str", "required": True}},
        "alignment_key": "market_size",
        "upstream": {"market_size": 500e9},
    })
    # 999e9 vs upstream 500e9 is far off -> alignment layer fails, gateway degrades
    assert r["ok"], r
    assert r["result"]["passed"] is False
    assert any(v is not None for k, v in r["result"]["layer_failures"].items() if k != 0)


def test_critic_plan_detects_cycle():
    r = run_tool("critic_plan", {
        "plan": {"plan_id": "m", "goal": "test",
                 "steps": [{"id": "a", "depends_on": ["b"]},
                            {"id": "b", "depends_on": ["a"]}]},
    })
    assert r["ok"], r
    assert r["result"]["sound"] is False
    assert len(r["result"]["repairs"]) >= 1


def test_critic_plan_closed_loop_converges():
    r = run_tool("critic_plan", {
        "plan": {"plan_id": "m", "goal": "test",
                 "steps": [{"id": "a", "depends_on": ["b"]},
                            {"id": "b", "depends_on": ["a"]}]},
        "closed_loop": True,
        "max_rounds": 3,
    })
    assert r["ok"], r
    assert r["result"]["converged"] is True
    assert r["result"]["rounds"] >= 1
    assert r["result"]["final_plan"] is not None


def test_trace_span_reports_similar():
    r = run_tool("trace_span", {
        "span_id": "s1",
        "input_text": "what is the 2024 market size",
        "output_text": "the 2024 market size is about 500 billion",
    })
    assert r["ok"], r
    res = r["result"]
    assert res["span_id"] == "s1"
    assert res["similarity"] > 0.3
    assert res["hallucination"] is False


def test_trace_span_hallucination_guard():
    r = run_tool("trace_span", {
        "span_id": "s2",
        "input_text": "what is the 2024 market size",
        "output_text": "the weather is nice today",
        "threshold": 0.3,
    })
    assert r["ok"], r
    assert r["result"]["hallucination"] is True


def test_route_task_tiers():
    easy = run_tool("route_task", {"depth": 1, "fan_in": 1,
                                    "risk": 0.1, "tokens": 200})
    hard = run_tool("route_task", {"depth": 8, "fan_in": 4,
                                    "risk": 0.9, "tokens": 3000,
                                    "requires_reasoning": True})
    assert easy["ok"] and hard["ok"], (easy, hard)
    assert easy["result"]["tier"] != hard["result"]["tier"]
    assert easy["result"]["cost"] < hard["result"]["cost"]


def test_route_task_with_cache_write():
    r = run_tool("route_task", {"depth": 2, "fan_in": 1, "risk": 0.4,
                                "tokens": 500,
                                "use_cache": True,
                                "cache_key": "unit-test-cache-key"})
    assert r["ok"], r
    assert r["result"]["cached"] is True


def test_unknown_tool_error_envelope():
    r = run_tool("definitely_not_a_tool", {})
    assert r["ok"] is False
    assert "unknown tool" in r["error"]
