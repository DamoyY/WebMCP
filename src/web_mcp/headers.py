from __future__ import annotations
from typing import Any
from mcp.server.fastmcp.exceptions import ToolError
from web_mcp.config import HeaderConfig


def require_header(context: Any, header_name: str) -> str:
    request = context.request_context.request
    if request is None:
        raise ToolError(f"Missing HTTP request context for header {header_name}")
    value = request.headers.get(header_name)
    if not value:
        raise ToolError(f"Missing required header: {header_name}")
    return value


def optional_header(context: Any, header_name: str) -> str | None:
    request = context.request_context.request
    if request is None:
        return None
    return request.headers.get(header_name) or None


def exa_api_key(context: Any, config: HeaderConfig) -> str:
    return require_header(context, config.exa_api_key)


def jina_api_key(context: Any, config: HeaderConfig) -> str:
    return require_header(context, config.jina_api_key)
