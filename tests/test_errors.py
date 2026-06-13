from __future__ import annotations
import pytest
from pydantic import BaseModel
from web_mcp.errors import ClientFacingError, validate_request_arguments
from web_mcp.models import FindArguments, OpenArguments, SearchQueryArguments


def test_validation_error_for_domains_string_is_safe_and_actionable() -> None:
    message = _validation_message(
        SearchQueryArguments, [{"q": "OpenAI", "domains": "openai.com"}]
    )
    assert "requests[0].domains must be an array" in message
    _assert_safe(message)


def test_validation_error_for_invalid_url_is_safe_and_actionable() -> None:
    message = _validation_message(OpenArguments, [{"url": "example.com"}])
    assert "requests[0].url must be an absolute HTTP or HTTPS URL" in message
    _assert_safe(message)


def test_validation_error_for_invalid_snippet_tokens_is_safe_and_actionable() -> None:
    message = _validation_message(
        FindArguments,
        [{"url": "https://example.com", "pattern": "Example", "snippet_tokens": 0}],
    )
    assert "requests[0].snippet_tokens must be greater than or equal to 1" in message
    _assert_safe(message)


def test_validation_error_for_missing_requests_is_safe_and_actionable() -> None:
    with pytest.raises(ClientFacingError) as error:
        validate_request_arguments(OpenArguments, None)
    message = str(error.value)
    assert message == "Invalid request: requests is required and must be an array"
    _assert_safe(message)


def _validation_message(arguments_model: type[BaseModel], requests: object) -> str:
    with pytest.raises(ClientFacingError) as error:
        validate_request_arguments(arguments_model, requests)
    return str(error.value)


def _assert_safe(message: str) -> None:
    forbidden_fragments = [
        "pydantic.dev",
        "ValidationError",
        "input_value",
        "input_type",
        "web_mcp",
        "Traceback",
    ]
    assert not any(fragment in message for fragment in forbidden_fragments)
