from app.core.config import get_settings
from app.mcp.oauth_provider import NotionOAuthClientProvider
from app.mcp.remote_client import RemoteMCPClient, is_write_tool


class NotionMCPClient(RemoteMCPClient):
    """Backward-compatible Notion client; new code should use PartnerRegistry."""

    def __init__(self):
        settings = get_settings()
        super().__init__(
            name="notion",
            display_name="Notion",
            server_url=settings.notion_mcp_url,
            token_file=settings.notion_mcp_token_file,
            timeout_seconds=settings.mcp_timeout_seconds,
            oauth_provider_cls=NotionOAuthClientProvider,
        )
