from typing import Any
import httpx
from pydantic import AnyUrl
from mcp import ClientSession
from app.mcp.oauth_provider import NotionOAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from app.core.config import get_settings
from app.mcp.oauth_storage import FileTokenStorage

WRITE_MARKERS = ("create", "update", "delete", "move", "duplicate", "comment", "append")
class NotionMCPError(RuntimeError): pass

async def _reauth_redirect(_: str):
    raise NotionMCPError("Notion authorization is required. Run: python scripts/notion_auth.py")
async def _reauth_callback():
    raise NotionMCPError("Interactive Notion authorization cannot run inside the API process. Run scripts/notion_auth.py")

class NotionMCPClient:
    def __init__(self): self.settings=get_settings()
    def _oauth(self):
        return NotionOAuthClientProvider(
            server_url=self.settings.notion_mcp_url,
            client_metadata=OAuthClientMetadata(client_name="Notion Partner Agent",redirect_uris=[AnyUrl("http://localhost:3030/callback")],grant_types=["authorization_code","refresh_token"],response_types=["code"]),
            storage=FileTokenStorage(self.settings.notion_mcp_token_file),redirect_handler=_reauth_redirect,callback_handler=_reauth_callback)
    async def list_tools(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(auth=self._oauth(),follow_redirects=True,timeout=self.settings.mcp_timeout_seconds) as http:
            async with streamable_http_client(self.settings.notion_mcp_url,http_client=http) as (read,write,_):
                async with ClientSession(read,write) as session:
                    await session.initialize(); result=await session.list_tools()
                    return [{"name":t.name,"description":t.description or "","inputSchema":t.inputSchema} for t in result.tools]
    async def call_tool(self,name:str,arguments:dict[str,Any])->dict[str,Any]:
        async with httpx.AsyncClient(auth=self._oauth(),follow_redirects=True,timeout=self.settings.mcp_timeout_seconds) as http:
            async with streamable_http_client(self.settings.notion_mcp_url,http_client=http) as (read,write,_):
                async with ClientSession(read,write) as session:
                    await session.initialize(); result=await session.call_tool(name,arguments)
                    content=[]
                    for item in result.content:
                        content.append({"type":getattr(item,"type","unknown"),"text":getattr(item,"text",str(item))})
                    return {"tool":name,"isError":bool(getattr(result,"isError",False)),"content":content}

def is_write_tool(name:str)->bool:
    n=name.lower(); return any(m in n for m in WRITE_MARKERS)
