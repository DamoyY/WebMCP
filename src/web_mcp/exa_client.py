from __future__ import annotations
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
import httpx
from exa_py import AsyncExa
from .config import SearchConfig
from .errors import ClientFacingError, http_service_error, upstream_timeout
from .models import SearchQueryRequest, SearchResult


class ExaSearchClient:
    def __init__(self, config: SearchConfig) -> None:
        self._config = config

    async def search_many(
        self, requests: list[SearchQueryRequest], api_key: str
    ) -> list[SearchResult]:
        client = AsyncExa(api_key)
        tasks = [self._search_one(client, request) for request in requests]
        query_results = await asyncio.gather(*tasks)
        return [result for results in query_results for result in results]

    async def _search_one(
        self, client: AsyncExa, request: SearchQueryRequest
    ) -> list[SearchResult]:
        try:
            response = await client.search(
                request.q,
                type=self._config.type,
                num_results=self._config.num_results,
                category=request.category,
                include_domains=_normalize_domains(request.domains),
                start_published_date=self._start_published_date(request.recency),
                contents={
                    "highlights": {
                        "query": request.q,
                        "max_characters": self._config.highlights_max_characters,
                    },
                    "max_age_hours": self._config.max_age_hours,
                    "livecrawl_timeout": self._config.livecrawl_timeout,
                },
            )
        except httpx.TimeoutException as error:
            raise upstream_timeout("Exa") from error
        except Exception as error:
            raise _to_exa_client_error(error) from error
        return [_to_search_result(result) for result in response.results]

    def _start_published_date(self, recency: int | None) -> str | None:
        if recency is None:
            return None
        return (datetime.now(UTC) - timedelta(days=recency)).date().isoformat()


def _normalize_domains(domains: list[str] | None) -> list[str] | None:
    if domains is None:
        return None
    normalized = [_normalize_domain(domain) for domain in domains]
    return [domain for domain in normalized if domain] or None


def _normalize_domain(domain: str) -> str:
    value = domain.strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc or parsed.path
    return host.split("/")[0].lower()


def _to_search_result(result: Any) -> SearchResult:
    highlights = getattr(result, "highlights", None) or []
    summary = "\n".join(str(highlight) for highlight in highlights)
    return SearchResult(
        title=getattr(result, "title", None),
        date=getattr(result, "published_date", None)
        or getattr(result, "publishedDate", None),
        url=str(result.url),
        summary=summary,
    )


def _to_exa_client_error(error: Exception) -> ClientFacingError:
    status_code = _status_code(error)
    if status_code is not None:
        return http_service_error("Exa", status_code)
    return ClientFacingError(
        "Exa search request failed. Check the API key header, query parameters, and retry."
    )


def _status_code(error: Exception) -> int | None:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None) or getattr(
        error, "status_code", None
    )
    return status_code if isinstance(status_code, int) else None
