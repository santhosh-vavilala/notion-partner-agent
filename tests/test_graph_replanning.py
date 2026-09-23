from types import SimpleNamespace

import pytest

from app.agent import graph as graph_module
from app.models.schemas import Intent, Risk, RouteDecision


@pytest.mark.asyncio
async def test_graph_replans_after_tool_access_before_search(monkeypatch):
    plans = [
        [{"name": "notion-get-tool-access", "arguments": {}}],
        [{"name": "notion-search", "arguments": {"query": "Partner Agent"}}],
        [],
    ]

    class FakeLLM:
        async def classify(self, _message):
            return RouteDecision(
                intent=Intent.SEARCH_KNOWLEDGE, risk=Risk.READ,
                objective="Find Partner Agent", requires_mcp=True,
            )

        async def select_tools(self, _message, _route, _tools, previous_calls, previous_results):
            assert len(previous_calls) == len(previous_results)
            return plans.pop(0)

        async def answer(self, _message, _route, results):
            assert [result["tool"] for result in results] == [
                "notion-get-tool-access", "notion-search",
            ]
            return "Found and summarized."

    class FakeMCP:
        async def list_tools(self):
            return [
                {"name": "notion-get-tool-access"},
                {"name": "notion-search"},
            ]

        async def call_tool(self, name, arguments):
            return {"tool": name, "isError": False, "content": [arguments]}

    monkeypatch.setattr(graph_module, "llm", FakeLLM())
    monkeypatch.setattr(graph_module, "mcp", FakeMCP())
    monkeypatch.setattr(graph_module, "settings", SimpleNamespace(
        max_mcp_tool_calls=4, require_write_approval=True,
    ))
    graph = graph_module.build_graph()

    result = await graph.ainvoke(
        {"message": "Search Partner Agent", "thread_id": "replan", "user_id": "test", "approve_write": False},
        config={"configurable": {"thread_id": "replan"}},
    )

    assert result["answer"] == "Found and summarized."
    assert [call["name"] for call in result["tool_calls"]] == [
        "notion-get-tool-access", "notion-search",
    ]
