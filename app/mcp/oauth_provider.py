from dataclasses import fields

from mcp.client.auth import OAuthClientProvider
from mcp.client.auth.oauth2 import OAuthContext


class _NotionOAuthContext(OAuthContext):
    def prepare_token_auth(self, data, headers=None):
        data, headers = super().prepare_token_auth(data, headers)
        # Notion rejects the SDK's duplicate client_id under HTTP Basic auth.
        # https://github.com/modelcontextprotocol/python-sdk/issues/3138
        if headers.get("Authorization", "").startswith("Basic "):
            data = {k: v for k, v in data.items() if k not in ("client_id", "client_secret")}
        return data, headers


class NotionOAuthClientProvider(OAuthClientProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = _NotionOAuthContext(
            **{field.name: getattr(self.context, field.name) for field in fields(OAuthContext)}
        )
