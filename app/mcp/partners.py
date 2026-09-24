from dataclasses import dataclass
from pathlib import Path

from mcp.client.auth import OAuthClientProvider

from app.core.config import Settings, get_settings
from app.mcp.oauth_provider import SingleMethodOAuthClientProvider
from app.mcp.remote_client import RemoteMCPClient


@dataclass(frozen=True)
class PartnerDefinition:
    name: str
    display_name: str
    server_url: str
    token_file: str
    oauth_provider_cls: type[OAuthClientProvider] = SingleMethodOAuthClientProvider

    @property
    def auth_command(self) -> str:
        return f"python -m scripts.partner_auth {self.name}"


@dataclass(frozen=True)
class PartnerSpec:
    name: str
    display_name: str
    url_setting: str
    token_setting: str
    oauth_provider_cls: type[OAuthClientProvider] = SingleMethodOAuthClientProvider


# Add future hosted OAuth MCP partners here and expose their two settings in Settings.
PARTNER_SPECS = (
    PartnerSpec("notion", "Notion", "notion_mcp_url", "notion_mcp_token_file"),
    PartnerSpec("linear", "Linear", "linear_mcp_url", "linear_mcp_token_file"),
)

SUPPORTED_PARTNERS = tuple(spec.name for spec in PARTNER_SPECS)


class PartnerRegistry:
    def __init__(self, definitions: list[PartnerDefinition], timeout_seconds: float):
        self._definitions = {definition.name: definition for definition in definitions}
        self._clients = {
            name: RemoteMCPClient(
                name=definition.name,
                display_name=definition.display_name,
                server_url=definition.server_url,
                token_file=definition.token_file,
                timeout_seconds=timeout_seconds,
                oauth_provider_cls=definition.oauth_provider_cls,
            )
            for name, definition in self._definitions.items()
        }

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    @property
    def definitions(self) -> tuple[PartnerDefinition, ...]:
        return tuple(self._definitions.values())

    def get(self, name: str) -> RemoteMCPClient:
        try:
            return self._clients[name]
        except KeyError as exc:
            raise ValueError(f"Unsupported partner: {name}") from exc

    def status(self) -> list[dict]:
        return [
            {
                "name": definition.name,
                "display_name": definition.display_name,
                "mcp_url": definition.server_url,
                "token_present": Path(definition.token_file).exists(),
                "auth_command": definition.auth_command,
            }
            for definition in self.definitions
        ]


def build_partner_registry(settings: Settings | None = None) -> PartnerRegistry:
    settings = settings or get_settings()
    return PartnerRegistry(
        definitions=[
            PartnerDefinition(
                name=spec.name,
                display_name=spec.display_name,
                server_url=getattr(settings, spec.url_setting),
                token_file=getattr(settings, spec.token_setting),
                oauth_provider_cls=spec.oauth_provider_cls,
            )
            for spec in PARTNER_SPECS
        ],
        timeout_seconds=settings.mcp_timeout_seconds,
    )
