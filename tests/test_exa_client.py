from __future__ import annotations
from datetime import UTC, datetime
from typing import Any, cast
import pytest
from exa_py import AsyncExa
from pydantic import ValidationError
import exa_client
from config import SearchConfig
from exa_client import ExaSearchClient, _normalize_domains
from models import SearchQueryRequest


def test_normalize_domains_accepts_list() -> None:
    assert _normalize_domains(["https://OpenAI.com/docs", "example.com"]) == [
        "openai.com",
        "example.com",
    ]


def test_search_query_request_rejects_domains_string() -> None:
    with pytest.raises(ValidationError):
        SearchQueryRequest.model_validate({"q": "OpenAI", "domains": "openai.com"})


def test_search_config_uses_24_hour_default_max_age() -> None:
    config = SearchConfig(
        num_results=15, type="deep-lite", highlights_max_characters=800
    )
    assert config.max_age_hours == 24


def test_search_config_uses_default_livecrawl_timeout() -> None:
    config = SearchConfig(
        num_results=15, type="deep-lite", highlights_max_characters=800
    )
    assert config.livecrawl_timeout == 30000


@pytest.mark.asyncio
async def test_search_includes_configured_livecrawl_timeout() -> None:
    client = _RecordingExaClient()
    config = SearchConfig(
        num_results=15,
        type="deep-lite",
        highlights_max_characters=800,
        livecrawl_timeout=12345,
    )
    await ExaSearchClient(config)._search_one(
        cast(AsyncExa, client), SearchQueryRequest(q="OpenAI")
    )
    assert client.kwargs is not None
    assert client.kwargs["contents"]["livecrawl_timeout"] == 12345


def test_start_published_date_uses_requested_recency_without_clamping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return cls(2026, 1, 15, tzinfo=UTC)

    monkeypatch.setattr(exa_client, "datetime", FixedDateTime)
    config = SearchConfig(
        num_results=15, type="deep-lite", highlights_max_characters=800
    )
    assert ExaSearchClient(config)._start_published_date(5000) == "2012-05-08"


class _ExaResult:
    title = "Example"
    published_date = None
    url = "https://example.com"
    highlights = ["Example highlight"]


class _ExaResponse:
    results = [_ExaResult()]


class _RecordingExaClient:
    kwargs: dict[str, Any] | None = None

    async def search(self, query: str, **kwargs: Any) -> _ExaResponse:
        self.kwargs = kwargs
        return _ExaResponse()
