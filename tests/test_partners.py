from types import SimpleNamespace

import pytest

from app.mcp.oauth_provider import SingleMethodOAuthClientProvider
from app.mcp.partners import SUPPORTED_PARTNERS, build_partner_registry


def test_registry_builds_isolated_partner_clients(tmp_path):
    settings = SimpleNamespace(
        notion_mcp_url="https://mcp.notion.com/mcp",
        notion_mcp_token_file=str(tmp_path / "notion_mcp_token.json"),
        linear_mcp_url="https://mcp.linear.app/mcp",
        linear_mcp_token_file=str(tmp_path / "linear_mcp_token.json"),
        mcp_timeout_seconds=12,
    )

    registry = build_partner_registry(settings)

    assert registry.names == SUPPORTED_PARTNERS == ("notion", "linear")
    assert registry.get("notion").token_file != registry.get("linear").token_file
    assert registry.get("linear").oauth_provider_cls is SingleMethodOAuthClientProvider
    assert [item["name"] for item in registry.status()] == ["notion", "linear"]


def test_registry_rejects_unknown_partner(tmp_path):
    settings = SimpleNamespace(
        notion_mcp_url="https://mcp.notion.com/mcp",
        notion_mcp_token_file=str(tmp_path / "notion.json"),
        linear_mcp_url="https://mcp.linear.app/mcp",
        linear_mcp_token_file=str(tmp_path / "linear.json"),
        mcp_timeout_seconds=12,
    )

    with pytest.raises(ValueError, match="Unsupported partner"):
        build_partner_registry(settings).get("unknown")
