"""One-time interactive OAuth bootstrap for Notion's hosted MCP."""
import asyncio, os
from urllib.parse import parse_qs, urlparse
import httpx
from pydantic import AnyUrl
from mcp import ClientSession
from app.mcp.oauth_provider import NotionOAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from app.mcp.oauth_storage import FileTokenStorage

SERVER=os.getenv("NOTION_MCP_URL","https://mcp.notion.com/mcp")
TOKEN_FILE=os.getenv("NOTION_MCP_TOKEN_FILE",".secrets/notion_mcp_token.json")
async def redirect(url:str): print("\nOpen this URL and authorize Notion:\n\n"+url+"\n")
async def callback():
    u=input("Paste the FULL callback URL from the browser address bar: ").strip(); q=parse_qs(urlparse(u).query)
    return q["code"][0], q.get("state",[None])[0]
async def main():
    oauth=NotionOAuthClientProvider(server_url=SERVER,client_metadata=OAuthClientMetadata(client_name="Notion Partner Agent",redirect_uris=[AnyUrl("http://localhost:3030/callback")],grant_types=["authorization_code","refresh_token"],response_types=["code"]),storage=FileTokenStorage(TOKEN_FILE),redirect_handler=redirect,callback_handler=callback)
    async with httpx.AsyncClient(auth=oauth,follow_redirects=True) as http:
        async with streamable_http_client(SERVER,http_client=http) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize(); tools=await session.list_tools(); print("Connected. MCP tools:",[t.name for t in tools.tools])
    print(f"Credentials saved under {TOKEN_FILE.rsplit('/',1)[0] if '/' in TOKEN_FILE else '.'}.")
if __name__=="__main__": asyncio.run(main())
