from __future__ import annotations
from web_mcp.input_normalization import WARNING_PREFIX, normalize_tool_arguments
from web_mcp.models import OpenArguments, OpenResponse, SearchQueryArguments


def test_normalize_tool_arguments_accepts_direct_open_object() -> None:
    result = normalize_tool_arguments(
        OpenArguments, {"URL": "example.com", "CHUNKS": 1}
    )
    assert result.requests == [{"url": "https://example.com", "chunk": 1}]
    assert result.warning is not None
    assert result.warning.startswith(WARNING_PREFIX)
    assert 'wrap the request object in the "requests" array' in result.warning
    assert 'use "url" instead of "URL"' in result.warning
    assert (
        'include a URL scheme for "request.url"; interpreted as "https://example.com"'
        in result.warning
    )
    assert 'use "chunk" instead of "CHUNKS"' in result.warning


def test_normalize_tool_arguments_accepts_search_aliases() -> None:
    result = normalize_tool_arguments(
        SearchQueryArguments,
        {
            "Request": {
                "Query": "OpenAI",
                "Domain": "openai.com",
                "Category": "Research Papers",
            }
        },
    )
    assert result.requests == [
        {"q": "OpenAI", "domains": ["openai.com"], "category": "research paper"}
    ]
    assert result.warning is not None
    assert 'use "requests" instead of "Request"' in result.warning
    assert 'pass "requests" as an array' in result.warning
    assert 'use "q" instead of "Query"' in result.warning
    assert 'use "domains" instead of "Domain"' in result.warning
    assert 'pass "requests[0].domains" as an array' in result.warning
    assert (
        'use "research paper" instead of "Research Papers" for "requests[0].category"'
        in result.warning
    )


def test_normalize_tool_arguments_does_not_warn_for_canonical_input() -> None:
    result = normalize_tool_arguments(
        OpenArguments, {"requests": [{"url": "https://example.com", "chunk": 1}]}
    )
    assert result.requests == [{"url": "https://example.com", "chunk": 1}]
    assert result.warning is None


def test_warning_is_omitted_from_response_without_normalization() -> None:
    warning = f'{WARNING_PREFIX}pass "requests" as an array.'
    assert OpenResponse(pages=[]).model_dump() == {"pages": []}
    assert OpenResponse(pages=[], warning=warning).model_dump() == {
        "pages": [],
        "warning": warning,
    }
