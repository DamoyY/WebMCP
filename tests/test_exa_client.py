from __future__ import annotations
import pytest
from pydantic import ValidationError
from web_mcp.exa_client import _normalize_domains
from web_mcp.models import SearchQueryRequest


def test_normalize_domains_accepts_list() -> None:
    assert _normalize_domains(["https://OpenAI.com/docs", "example.com"]) == [
        "openai.com",
        "example.com",
    ]


def test_search_query_request_rejects_domains_string() -> None:
    with pytest.raises(ValidationError):
        SearchQueryRequest.model_validate({"q": "OpenAI", "domains": "openai.com"})
