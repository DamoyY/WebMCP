from __future__ import annotations
import argparse
import asyncio
import os
from typing import Any
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def run_smoke_test(url: str) -> None:
    exa_key = os.environ["WEB_MCP_EXA_API_KEY"]
    jina_key = os.environ["WEB_MCP_JINA_API_KEY"]
    headers = {"x-exa-api-key": exa_key, "x-jina-api-key": jina_key}
    timeout = httpx.Timeout(30.0, read=120.0)
    async with (
        httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True
        ) as client,
        streamable_http_client(url, http_client=client) as streams,
    ):
        read_stream, write_stream = streams[0], streams[1]
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = sorted(tool.name for tool in tools.tools)
            print(f"tools={tool_names}")
            await _call_and_print(
                session,
                "search_query",
                {
                    "requests": [
                        {
                            "q": "OpenAI API docs",
                            "domains": ["openai.com"],
                            "recency": 30,
                            "category": "news",
                        }
                    ]
                },
            )
            await _call_and_print(
                session,
                "open",
                {"requests": [{"url": "https://example.com", "chunk": 1}]},
            )
            await _call_and_print(
                session,
                "find",
                {
                    "requests": [
                        {
                            "url": "https://example.com",
                            "pattern": "Example Domain",
                            "snippet_tokens": 20,
                        }
                    ]
                },
            )


async def _call_and_print(
    session: ClientSession, name: str, arguments: dict[str, Any]
) -> None:
    result = await session.call_tool(name, arguments)
    structured = result.structuredContent or {}
    print(f"{name}=ok keys={list(structured.keys())}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    args = parser.parse_args()
    asyncio.run(run_smoke_test(args.url))


if __name__ == "__main__":
    main()
