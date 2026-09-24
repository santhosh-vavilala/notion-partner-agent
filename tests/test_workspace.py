from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.models.schemas import ChatRequest, Intent
from app.services import agent_service


def test_workspace_assets_and_public_status(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(
        openai_api_key="private-test-key", openai_model="test-model",
        notion_mcp_token_file=str(tmp_path / "absent-token.json"),
        app_env="test", notion_mcp_url="https://mcp.notion.com/mcp",
        linear_mcp_token_file=str(tmp_path / "linear-token.json"),
        linear_mcp_url="https://mcp.linear.app/mcp",
        require_write_approval=True, max_mcp_tool_calls=4, mcp_timeout_seconds=45,
    ))
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert 'id="chat-form"' in page.text
        for asset in ("app.js", "style.css", "mark.svg"):
            assert client.get(f"/static/{asset}").status_code == 200
        response = client.get("/v1/status")
        assert response.status_code == 200
        assert response.json()["openai_configured"] is True
        partners = {partner["name"]: partner for partner in response.json()["partners"]}
        assert partners["notion"]["token_present"] is False
        assert partners["linear"]["token_present"] is False
        assert "private-test-key" not in response.text
        assert "openai_api_key" not in response.json()


def test_dependency_error_unwraps_task_group():
    error = ExceptionGroup("task group failed", [RuntimeError("Notion authorization is required")])
    assert routes.dependency_error_detail(error) == "RuntimeError: Notion authorization is required"


@pytest.mark.asyncio
@pytest.mark.parametrize("approval_required", [True, False])
async def test_response_exposes_review_and_execution_details(monkeypatch, approval_required):
    proposed = [{"name": "notion-create-pages", "arguments": {"title": "Test"}}]
    results = [{"tool": "notion-create-pages", "isError": False, "content": []}]

    async def invoke(state, config):
        assert state["approve_write"] is (not approval_required)
        return {
            "route": SimpleNamespace(intent=Intent.CREATE, partner="notion"),
            "answer": "Approval required" if approval_required else "Created",
            "selected_tools": proposed, "approval_required": approval_required,
            "tool_calls": [] if approval_required else proposed,
            "tool_results": [] if approval_required else results,
        }

    monkeypatch.setattr(agent_service, "graph", SimpleNamespace(ainvoke=invoke))
    result = await agent_service.AgentService().chat(ChatRequest(
        message="Create a page", thread_id="test", user_id="test",
        approve_write=not approval_required,
    ))
    assert result.planned_tools == (proposed if approval_required else [])
    assert result.tool_results == ([] if approval_required else results)
    assert result.trace_id
