from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from app.mcp.oauth_storage import FileTokenStorage


WRITE_MARKERS = (
    "create", "update", "delete", "move", "duplicate", "comment", "append",
    "write", "assign", "archive", "upload", "copy", "remove", "add_",
)


def is_write_tool(name: str) -> bool:
    normalized = name.lower()
    return any(marker in normalized for marker in WRITE_MARKERS)


class PartnerMCPError(RuntimeError):
    pass


class RemoteMCPClient:
    """Reusable Streamable HTTP MCP client for one configured partner."""

    def __init__(
        self,
        *,
        name: str,
        display_name: str,
        server_url: str,
        token_file: str,
        timeout_seconds: float,
        oauth_provider_cls: type[OAuthClientProvider] = OAuthClientProvider,
        callback_url: str = "http://localhost:3030/callback",
    ):
        self.name = name
        self.display_name = display_name
        self.server_url = server_url
        self.token_file = token_file
        self.timeout_seconds = timeout_seconds
        self.oauth_provider_cls = oauth_provider_cls
        self.callback_url = callback_url

    def oauth(
        self,
        redirect_handler: Callable[[str], Awaitable[None]],
        callback_handler: Callable[[], Awaitable[tuple[str, str | None]]],
    ) -> OAuthClientProvider:
        return self.oauth_provider_cls(
            server_url=self.server_url,
            client_metadata=OAuthClientMetadata(
                client_name=f"Partner Agent - {self.display_name}",
                redirect_uris=[AnyUrl(self.callback_url)],
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
            ),
            storage=FileTokenStorage(self.token_file),
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
        )

    async def _reauth_redirect(self, _: str):
        raise PartnerMCPError(
            f"{self.display_name} authorization is required. "
            f"Run: python -m scripts.partner_auth {self.name}"
        )

    async def _reauth_callback(self):
        raise PartnerMCPError(
            f"Interactive {self.display_name} authorization cannot run inside the API process. "
            f"Run: python -m scripts.partner_auth {self.name}"
        )

    def api_oauth(self) -> OAuthClientProvider:
        return self.oauth(self._reauth_redirect, self._reauth_callback)

    async def list_tools(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            auth=self.api_oauth(), follow_redirects=True, timeout=self.timeout_seconds,
        ) as http:
            async with streamable_http_client(self.server_url, http_client=http) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "inputSchema": tool.inputSchema,
                        }
                        for tool in result.tools
                    ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            auth=self.api_oauth(), follow_redirects=True, timeout=self.timeout_seconds,
        ) as http:
            async with streamable_http_client(self.server_url, http_client=http) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
                    content = [
                        {
                            "type": getattr(item, "type", "unknown"),
                            "text": getattr(item, "text", str(item)),
                        }
                        for item in result.content
                    ]
                    return {
                        "partner": self.name,
                        "tool": name,
                        "isError": bool(getattr(result, "isError", False)),
                        "content": content,
                    }
