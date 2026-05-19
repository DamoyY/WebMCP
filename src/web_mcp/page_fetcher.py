from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from web_mcp.config import AppConfig
from web_mcp.direct_fetch import fetch_direct_text, resolve_direct_fetch_target
from web_mcp.errors import ClientFacingError
from web_mcp.jina_client import JinaReaderClient


@dataclass(frozen=True)
class PageContent:
    url: str
    source: Literal["jina", "direct"]
    markdown: str


class PageFetcher:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._jina = JinaReaderClient(config.jina, config.http)

    async def fetch(self, url: str, jina_api_key: str | None) -> PageContent:
        target = resolve_direct_fetch_target(url, self._config.direct_fetch)
        if target is not None:
            markdown = await fetch_direct_text(
                target, self._config.direct_fetch, self._config.http
            )
            return PageContent(url=url, source="direct", markdown=markdown)
        if not jina_api_key:
            raise ClientFacingError(
                f"Missing required header: {self._config.headers.jina_api_key}. Non-direct URLs require a Jina API key."
            )
        markdown = await self._jina.read_markdown(url, jina_api_key)
        return PageContent(url=url, source="jina", markdown=markdown)
