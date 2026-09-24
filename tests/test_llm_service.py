import json
from types import SimpleNamespace

import pytest

from app.llm.openai_client import LLMService
from app.models.schemas import Intent, Risk, RouteDecision


@pytest.mark.asyncio
async def test_tool_plan_uses_strict_schema_and_decodes_arguments():
    captured = {}

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output_text=json.dumps({
            "calls": [{
                "name": "notion-search",
                "arguments_json": json.dumps({"query": "Partner Agent"}),
            }]
        }))

    service = LLMService()
    service._client = SimpleNamespace(responses=SimpleNamespace(create=create))
    route = RouteDecision(
        intent=Intent.SEARCH,
        risk=Risk.READ,
        objective="Find Partner Agent architecture",
        requires_mcp=True,
    )

    calls = await service.select_tools("Find Partner Agent", route, [{
        "name": "notion-search",
        "description": "Search Notion",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }])

    item_schema = captured["text"]["format"]["schema"]["properties"]["calls"]["items"]
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["arguments_json"]["type"] == "string"
    assert calls == [{"name": "notion-search", "arguments": {"query": "Partner Agent"}}]


@pytest.mark.asyncio
async def test_tool_plan_drops_invalid_argument_json():
    async def create(**_):
        return SimpleNamespace(output_text=json.dumps({
            "calls": [{"name": "notion-search", "arguments_json": "not json"}]
        }))

    service = LLMService()
    service._client = SimpleNamespace(responses=SimpleNamespace(create=create))
    route = RouteDecision(
        intent=Intent.SEARCH,
        risk=Risk.READ,
        objective="Search",
        requires_mcp=True,
    )

    assert await service.select_tools("Search", route, []) == []
