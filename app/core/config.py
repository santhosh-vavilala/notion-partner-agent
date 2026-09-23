from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "notion-partner-agent"
    openai_api_key: str
    openai_model: str = "gpt-5"
    notion_mcp_url: str = "https://mcp.notion.com/mcp"
    notion_mcp_token_file: str = ".secrets/notion_mcp_token.json"
    database_url: str | None = None
    log_level: str = "INFO"
    mcp_timeout_seconds: float = 45.0
    max_mcp_tool_calls: int = 4
    require_write_approval: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
