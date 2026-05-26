from __future__ import annotations
import asyncio
import re
from collections.abc import Awaitable
from typing import Any, ClassVar
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, ConfigDict, model_validator
from chunking import TokenChunker
from config import AppConfig, FindConfig
from errors import ClientFacingError, to_tool_exception, validate_request_arguments
from exa_client import ExaSearchClient
from headers import exa_api_key, optional_header
from input_normalization import normalize_tool_arguments
from models import (
    FindArguments,
    FindMatch,
    FindPage,
    FindResponse,
    OpenArguments,
    OpenResponse,
    SearchQueryArguments,
    SearchQueryResponse,
)
from open_chunks import normalize_open_chunk_requests, open_page_chunk
from page_fetcher import PageContent, PageFetcher


def register_tools(mcp: FastMCP, config: AppConfig) -> None:
    chunker = TokenChunker(config.chunking)
    page_fetcher = PageFetcher(config)
    search_client = ExaSearchClient(config.search)

    @mcp.tool(name="search_query")
    async def search_query(
        ctx: Context, requests: Any = None, warning: list[str] | None = None
    ) -> SearchQueryResponse:
        """返回标题、日期、URL 与摘要。"""
        try:
            arguments = validate_request_arguments(SearchQueryArguments, requests)
            key = exa_api_key(ctx, config.headers)
            results = await search_client.search_many(arguments.requests, key)
            return SearchQueryResponse(results=results, warning=warning)
        except Exception as error:
            raise to_tool_exception("search_query", error) from None

    @mcp.tool(name="open")
    async def open_pages(
        ctx: Context, requests: Any = None, warning: list[str] | None = None
    ) -> OpenResponse:
        """用于读取页面内容。"""
        try:
            warnings = list(warning or [])
            normalized_requests = normalize_open_chunk_requests(requests, warnings)
            arguments = validate_request_arguments(OpenArguments, normalized_requests)
            jina_key = optional_header(ctx, config.headers.jina_api_key)
            pages = await _fetch_pages(page_fetcher, arguments.requests, jina_key)
            opened = []
            for index, (request, page) in enumerate(
                zip(arguments.requests, pages, strict=True)
            ):
                opened.append(
                    open_page_chunk(page, request.chunk, index, chunker, warnings)
                )
            return OpenResponse(pages=opened, warning=warnings or None)
        except Exception as error:
            raise to_tool_exception("open", error) from None

    @mcp.tool(name="find")
    async def find(
        ctx: Context, requests: Any = None, warning: list[str] | None = None
    ) -> FindResponse:
        """在页面中使用正则表达式查找匹配片段。"""
        try:
            arguments = validate_request_arguments(FindArguments, requests)
            patterns = [
                _compile_pattern(request.pattern) for request in arguments.requests
            ]
            jina_key = optional_header(ctx, config.headers.jina_api_key)
            pages = await _fetch_pages(page_fetcher, arguments.requests, jina_key)
            found = []
            warnings = list(warning or [])
            for index, (request, page, pattern) in enumerate(
                zip(arguments.requests, pages, patterns, strict=True)
            ):
                snippet_tokens = _snippet_tokens_for_request(
                    request,
                    config.chunking.chunk_tokens,
                    config.find.default_snippet_tokens,
                    index,
                    warnings,
                )
                found.append(
                    _find_in_page(page, pattern, snippet_tokens, chunker, config.find)
                )
            return FindResponse(pages=found, warning=warnings or None)
        except Exception as error:
            raise to_tool_exception("find", error) from None

    _set_tool_input_model(mcp, "search_query", SearchQueryArguments)
    _set_tool_input_model(mcp, "open", OpenArguments)
    _set_tool_input_model(mcp, "find", FindArguments)


async def _fetch_pages(
    page_fetcher: PageFetcher, requests: list[Any], jina_key: str | None
) -> list[PageContent]:
    fetches: list[Awaitable[PageContent]] = [
        page_fetcher.fetch(request.url, jina_key) for request in requests
    ]
    return list(await asyncio.gather(*fetches))


def _find_in_page(
    page: PageContent,
    regex: re.Pattern[str],
    snippet_tokens: int,
    chunker: TokenChunker,
    find_config: FindConfig,
) -> FindPage:
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
        raise ClientFacingError(
            f"pattern is not a valid regular expression: {error}"
        ) from error


def _snippet_tokens_for_request(
    request: Any,
    chunk_tokens: int,
    default_snippet_tokens: int,
    request_index: int,
    warnings: list[str],
) -> int:
    if request.snippet_tokens is None:
        return default_snippet_tokens
    if request.snippet_tokens <= chunk_tokens:
        return request.snippet_tokens
    warnings.append(
        f'"requests[{request_index}].snippet_tokens" exceeds chunk_tokens '
        f"({chunk_tokens}); using {chunk_tokens}"
    )
    return chunk_tokens


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


class _TolerantToolArguments(ArgModelBase):
    requests: Any = None
    warning: list[str] | None = None
    arguments_model: ClassVar[type[BaseModel]]
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    @model_validator(mode="before")
    @classmethod
    def normalize_arguments(cls, data: Any) -> dict[str, Any]:
        result = normalize_tool_arguments(cls.arguments_model, data)
        return {"requests": result.requests, "warning": result.warning}


class _SearchQueryToolArguments(_TolerantToolArguments):
    arguments_model: ClassVar[type[BaseModel]] = SearchQueryArguments


class _OpenToolArguments(_TolerantToolArguments):
    arguments_model: ClassVar[type[BaseModel]] = OpenArguments


class _FindToolArguments(_TolerantToolArguments):
    arguments_model: ClassVar[type[BaseModel]] = FindArguments


_TOOL_ARGUMENT_MODELS: dict[str, type[_TolerantToolArguments]] = {
    "search_query": _SearchQueryToolArguments,
    "open": _OpenToolArguments,
    "find": _FindToolArguments,
}


def _set_tool_input_model(
    mcp: FastMCP, tool_name: str, arguments_model: type[BaseModel]
) -> None:
    manager = getattr(mcp, "_tool_manager", None)
    tool = manager.get_tool(tool_name) if manager is not None else None
    if tool is None:
        raise RuntimeError(f"tool {tool_name} was not registered")
    tool.parameters = arguments_model.model_json_schema()
    tool.fn_metadata.arg_model = _TOOL_ARGUMENT_MODELS[tool_name]
