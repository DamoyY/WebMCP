from __future__ import annotations
from datetime import UTC, datetime
import pytest
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
        num_results=15,
        type="deep-lite",
        highlights_max_characters=800,
    )
    assert config.max_age_hours == 24


def test_start_published_date_uses_requested_recency_without_clamping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return cls(2026, 1, 15, tzinfo=UTC)

    monkeypatch.setattr(exa_client, "datetime", FixedDateTime)
    config = SearchConfig(
        num_results=15,
        type="deep-lite",
        highlights_max_characters=800,
    )
    assert ExaSearchClient(config)._start_published_date(5000) == "2012-05-08"
