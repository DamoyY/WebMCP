from __future__ import annotations
import logging
from collections.abc import Mapping, Sequence
from typing import Any, TypeVar
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)
TArguments = TypeVar("TArguments", bound=BaseModel)


class ClientFacingError(ValueError):
    pass


def validate_request_arguments(
    arguments_model: type[TArguments], raw_requests: Any
) -> TArguments:
    if raw_requests is None:
        raise ClientFacingError(
            "Invalid request: requests is required and must be an array"
        )
    try:
        return arguments_model.model_validate({"requests": raw_requests})
    except ValidationError as error:
        raise ClientFacingError(_format_validation_error(error)) from error


def to_tool_exception(tool_name: str, error: Exception) -> Exception:
    if isinstance(error, ClientFacingError):
        return ValueError(str(error))
    logger.exception("Unhandled %s tool error", tool_name)
    return RuntimeError(
        "Unexpected server error. Retry the request or contact the service operator."
    )


def http_service_error(service: str, status_code: int) -> ClientFacingError:
    if status_code in {401, 403}:
        return ClientFacingError(
            f"{service} request was rejected. Check the API key header and permissions."
        )
    if status_code == 429:
        return ClientFacingError(
            f"{service} rate limit was reached. Retry later or use another API key."
        )
    if 400 <= status_code < 500:
        return ClientFacingError(
            f"{service} rejected the request with HTTP {status_code}. Check the input URL and parameters."
        )
    return ClientFacingError(
        f"{service} returned HTTP {status_code}. Retry later or contact the upstream service."
    )


def upstream_unreachable(service: str) -> ClientFacingError:
    return ClientFacingError(
        f"Could not reach {service}. Check network connectivity and retry."
    )


def upstream_timeout(service: str) -> ClientFacingError:
    return ClientFacingError(f"{service} request timed out. Retry later.")


def _format_validation_error(error: ValidationError) -> str:
    messages = [_format_single_validation_issue(issue) for issue in error.errors()]
    return "Invalid request: " + "; ".join(messages[:5])


def _format_single_validation_issue(issue: Mapping[str, Any]) -> str:
    raw_location = issue.get("loc", ())
    location = _format_location(
        raw_location if isinstance(raw_location, Sequence) else ()
    )
    issue_type = str(issue.get("type", ""))
    raw_context = issue.get("ctx")
    context: Mapping[str, Any] = raw_context if isinstance(raw_context, dict) else {}
    message = str(issue.get("msg", "is invalid"))
    if issue_type == "missing":
        return f"{location} is required"
    if issue_type in {"list_type", "tuple_type"}:
        return f"{location} must be an array"
    if issue_type == "model_type":
        return f"{location} must be an object"
    if issue_type == "string_type":
        return f"{location} must be a string"
    if issue_type == "string_too_short":
        return f"{location} must not be empty"
    if issue_type in {"int_type", "int_parsing"}:
        return f"{location} must be an integer"
    if issue_type == "greater_than_equal":
        return f"{location} must be greater than or equal to {context.get('ge')}"
    if issue_type == "literal_error":
        return f"{location} must be one of {_expected_values(context)}"
    if issue_type == "extra_forbidden":
        return f"{location} is not supported"
    if issue_type == "value_error":
        return f"{location} {_clean_value_error(message)}"
    return f"{location} {message}"


def _format_location(location: Sequence[Any]) -> str:
    if not location:
        return "request"
    rendered = "request"
    for part in location:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            if rendered == "request" and part == "requests":
                rendered = "requests"
            else:
                rendered += f".{part}"
    return rendered


def _expected_values(context: Mapping[str, Any]) -> str:
    expected = str(context.get("expected", "")).replace(" or ", ", ")
    return expected or "the documented values"


def _clean_value_error(message: str) -> str:
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message
