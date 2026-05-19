from __future__ import annotations
import asyncio
import re
from collections.abc import Awaitable
from typing import Any
from mcp.server.fastmcp import Context, FastMCP
from web_mcp.chunking import TokenChunker
from web_mcp.config import AppConfig, FindConfig
from web_mcp.exa_client import ExaSearchClient
from web_mcp.headers import exa_api_key, optional_header
from web_mcp.models import (
    FindMatch,
    FindPage,
    FindRequest,
    FindResponse,
    OpenPage,
    OpenRequest,
    OpenResponse,
    SearchQueryRequest,
    SearchQueryResponse,
)
from web_mcp.page_fetcher import PageContent, PageFetcher


def register_tools(mcp: FastMCP, config: AppConfig) -> None:
    chunker = TokenChunker(config.chunking)
    page_fetcher = PageFetcher(config)
    search_client = ExaSearchClient(config.search)

    @mcp.tool(name="search_query")
    async def search_query(
        requests: list[SearchQueryRequest], ctx: Context
    ) -> SearchQueryResponse:
        """返回标题、日期、URL 与摘要。"""
        key = exa_api_key(ctx, config.headers)
        results = await search_client.search_many(requests, key)
        return SearchQueryResponse(results=results)

    @mcp.tool(name="open")
    async def open_pages(requests: list[OpenRequest], ctx: Context) -> OpenResponse:
        """用于读取页面内容。"""
        jina_key = optional_header(ctx, config.headers.jina_api_key)
        pages = await _fetch_pages(page_fetcher, requests, jina_key)
        opened = []
        for request, page in zip(requests, pages, strict=True):
            chunk, total_chunks, _token_count = chunker.select(
                page.markdown, request.chunk
            )
            opened.append(
                OpenPage(
                    chunk=chunk.index, total_chunks=total_chunks, content=chunk.content
                )
            )
        return OpenResponse(pages=opened)

    @mcp.tool(name="find")
    async def find(requests: list[FindRequest], ctx: Context) -> FindResponse:
        """在页面中使用正则表达式查找匹配片段。"""
        jina_key = optional_header(ctx, config.headers.jina_api_key)
        pages = await _fetch_pages(page_fetcher, requests, jina_key)
        found = []
        for request, page in zip(requests, pages, strict=True):
            found.append(
                _find_in_page(
                    page,
                    request.pattern,
                    request.snippet_tokens or config.find.default_snippet_tokens,
                    chunker,
                    config.find,
                )
            )
        return FindResponse(pages=found)


async def _fetch_pages(
    page_fetcher: PageFetcher, requests: list[Any], jina_key: str | None
) -> list[PageContent]:
    fetches: list[Awaitable[PageContent]] = [
        page_fetcher.fetch(request.url, jina_key) for request in requests
    ]
    return list(await asyncio.gather(*fetches))


def _find_in_page(
    page: PageContent,
    pattern: str,
    snippet_tokens: int,
    chunker: TokenChunker,
    find_config: FindConfig,
) -> FindPage:
    regex = _compile_pattern(pattern)
    chunks = chunker.split(page.markdown)
    matches: list[FindMatch] = []
    for chunk in chunks:
        for match in regex.finditer(chunk.content):
            matches.append(
                _match_to_output(
                    chunk.index, chunk.content, match, snippet_tokens, chunker
                )
            )
            if len(matches) >= find_config.max_matches_per_page:
                return FindPage(total_chunks=len(chunks), matches=matches)
    return FindPage(total_chunks=len(chunks), matches=matches)


def _compile_pattern(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern, re.MULTILINE)
    except re.error as error:
        raise ValueError(f"invalid regex pattern: {error}") from error


def _match_to_output(
    chunk_index: int,
    content: str,
    match: re.Match[str],
    snippet_tokens: int,
    chunker: TokenChunker,
) -> FindMatch:
    return FindMatch(
        chunk=chunk_index,
        snippet=chunker.snippet_around_span(
            content, match.start(), match.end(), snippet_tokens
        ),
    )
