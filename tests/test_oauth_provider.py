from urllib.parse import parse_qs

import httpx
import pytest
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

from app.mcp.oauth_provider import NotionOAuthClientProvider
from app.mcp.oauth_storage import FileTokenStorage


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["client_secret_basic", "client_secret_post", "none"])
async def test_token_requests_use_one_authentication_method(tmp_path, method):
    provider = NotionOAuthClientProvider(
        server_url="https://mcp.notion.com/mcp",
        client_metadata=OAuthClientMetadata(redirect_uris=["http://localhost:3030/callback"]),
        storage=FileTokenStorage(str(tmp_path / "token.json")),
    )
    provider.context.client_info = OAuthClientInformationFull(
        client_id="test-client", client_secret="test-secret",
        redirect_uris=["http://localhost:3030/callback"],
        token_endpoint_auth_method=method,
    )
    provider.context.current_tokens = OAuthToken(
        access_token="test-access", token_type="Bearer", refresh_token="test-refresh",
    )
    exchange = await provider._exchange_token_authorization_code("test-code", "test-verifier")
    refresh = await provider._refresh_token()
    for request in (exchange, refresh):
        form = parse_qs(request.content.decode())
        if method == "client_secret_basic":
            expected = httpx.BasicAuth("test-client", "test-secret")
            auth_request = next(expected.auth_flow(httpx.Request("POST", request.url)))
            assert request.headers["Authorization"] == auth_request.headers["Authorization"]
            assert "client_id" not in form
            assert "client_secret" not in form
        else:
            assert "Authorization" not in request.headers
            assert form["client_id"] == ["test-client"]
            assert form.get("client_secret") == (["test-secret"] if method == "client_secret_post" else None)
    assert parse_qs(exchange.content.decode())["code_verifier"] == ["test-verifier"]
    assert parse_qs(refresh.content.decode())["refresh_token"] == ["test-refresh"]
