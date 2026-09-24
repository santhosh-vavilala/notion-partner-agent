"""Interactive OAuth bootstrap for any configured partner MCP server."""

import argparse
import asyncio
from urllib.parse import parse_qs, urlparse

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.mcp.partners import build_partner_registry


async def authorize(partner_name: str):
    registry = build_partner_registry()
    client = registry.get(partner_name)

    async def redirect(url: str):
        print(f"\nOpen this URL and authorize {client.display_name}:\n\n{url}\n")

    async def callback():
        callback_url = input("Paste the FULL callback URL from the browser address bar: ").strip()
        query = parse_qs(urlparse(callback_url).query)
        if "code" not in query:
            raise RuntimeError("The callback URL does not contain an authorization code.")
        return query["code"][0], query.get("state", [None])[0]

    oauth = client.oauth(redirect, callback)
    async with httpx.AsyncClient(
        auth=oauth, follow_redirects=True, timeout=client.timeout_seconds,
    ) as http:
        async with streamable_http_client(client.server_url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                print("Connected. MCP tools:", [tool.name for tool in tools.tools])
    print(f"{client.display_name} credentials saved under {client.token_file}.")


def main():
    registry = build_partner_registry()
    parser = argparse.ArgumentParser(description="Authorize a configured partner MCP server.")
    parser.add_argument("partner", choices=registry.names)
    args = parser.parse_args()
    asyncio.run(authorize(args.partner))


if __name__ == "__main__":
    main()
