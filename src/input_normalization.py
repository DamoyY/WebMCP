from __future__ import annotations
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel
from input_aliases import (
    field_lookup,
    field_path,
    list_item_type,
    literal_string_values,
    looks_like_model,
    matching_key,
    model_type,
    name_aliases,
    parse_json_container,
    request_model,
    singularize,
)

SITE_QUERY_PATTERN = re.compile(r"(?<!\w)site\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class NormalizationResult:
    requests: Any
    warning: list[str] | None


def normalize_tool_arguments(
    arguments_model: type[BaseModel], raw_arguments: Any
) -> NormalizationResult:
    warnings = _WarningBuilder()
    data = parse_json_container(raw_arguments)
    if isinstance(data, Mapping):
        requests_key = matching_key(arguments_model, data, "requests")
        if requests_key is not None:
            if requests_key != "requests":
                warnings.add(f'use "requests" instead of "{requests_key}"')
            _warn_unused_model_fields(
                arguments_model, data, {requests_key}, warnings, ""
            )
            normalized_requests = _normalize_model_field(
                arguments_model, "requests", data[requests_key], warnings, "requests"
            )
            return NormalizationResult(
                requests=normalized_requests, warning=warnings.message()
            )
        item_model = request_model(arguments_model)
        if looks_like_model(item_model, data):
            warnings.add('wrap the request object in the "requests" array')
            normalized_request = _normalize_model_value(
                item_model, data, warnings, "request"
            )
            return NormalizationResult(
                requests=[normalized_request], warning=warnings.message()
            )
        return NormalizationResult(requests=None, warning=None)
    normalized_requests = _normalize_model_field(
        arguments_model, "requests", data, warnings, "requests"
    )
    return NormalizationResult(requests=normalized_requests, warning=warnings.message())


class _WarningBuilder:
    def __init__(self) -> None:
        self._messages: list[str] = []

    def add(self, message: str) -> None:
        if message not in self._messages:
            self._messages.append(message)

    def message(self) -> list[str] | None:
        if not self._messages:
            return None
        return list(self._messages)


def _normalize_model_value(
    model: type[BaseModel], raw_value: Any, warnings: _WarningBuilder, path: str
) -> Any:
    value = parse_json_container(raw_value)
    if not isinstance(value, Mapping):
        return value
    lookup = field_lookup(model)
    normalized: dict[Any, Any] = {}
    for raw_key, raw_item in value.items():
        if not isinstance(raw_key, str):
            warnings.add(f'ignored unrecognized field "{field_path(path, raw_key)}"')
            continue
        canonical = lookup.get(raw_key.lower())
        if canonical is None:
            warnings.add(f'ignored unrecognized field "{field_path(path, raw_key)}"')
            continue
        if canonical != raw_key:
            warnings.add(f'use "{canonical}" instead of "{raw_key}"')
        normalized_item = _normalize_model_field(
            model, canonical, raw_item, warnings, f"{path}.{canonical}"
        )
        if canonical in normalized:
            warnings.add(
                f'multiple aliases for "{canonical}" were provided; the last value was used'
            )
        normalized[canonical] = normalized_item
    return normalized


def _normalize_model_field(
    model: type[BaseModel],
    field_name: str,
    raw_value: Any,
    warnings: _WarningBuilder,
    path: str,
) -> Any:
    field = model.model_fields[field_name]
    item_type = list_item_type(field.annotation)
    value = parse_json_container(raw_value)
    if item_type is not None:
        if value is None:
            return value
        if not isinstance(value, list):
            value = [value]
            warnings.add(f'pass "{path}" as an array')
        normalized_items: list[Any] = []
        for index, item in enumerate(value):
            normalized_item = _normalize_value_for_annotation(
                item_type, field_name, item, warnings, f"{path}[{index}]"
            )
            normalized_items.append(normalized_item)
        return normalized_items
    return _normalize_value_for_annotation(
        field.annotation, field_name, value, warnings, path
    )


def _normalize_value_for_annotation(
    annotation: Any,
    field_name: str,
    raw_value: Any,
    warnings: _WarningBuilder,
    path: str,
) -> Any:
    model = model_type(annotation)
    if model is not None:
        return _normalize_model_value(model, raw_value, warnings, path)
    value = _normalize_url(field_name, raw_value, warnings, path)
    value = _normalize_literal(annotation, value, warnings, path)
    _warn_site_query(field_name, value, warnings, path)
    return value


def _normalize_url(
    field_name: str, value: Any, warnings: _WarningBuilder, path: str
) -> Any:
    if not isinstance(value, str) or singularize(field_name).lower() != "url":
        return value
    trimmed = value.strip()
    if trimmed != value:
        warnings.add(f'remove surrounding whitespace from "{path}"')
    if not trimmed or "://" in trimmed:
        return trimmed
    normalized = f"https://{trimmed}"
    warnings.add(f'include a URL scheme for "{path}"; interpreted as "{normalized}"')
    return normalized


def _normalize_literal(
    annotation: Any, value: Any, warnings: _WarningBuilder, path: str
) -> Any:
    if not isinstance(value, str):
        return value
    literals = literal_string_values(annotation)
    if not literals:
        return value
    lookup: dict[str, str] = {}
    for literal in literals:
        for alias in name_aliases(literal):
            lookup[alias.lower()] = literal
    normalized = lookup.get(value.strip().lower())
    if normalized is None:
        return value
    if normalized != value:
        warnings.add(f'use "{normalized}" instead of "{value}" for "{path}"')
    return normalized


def _warn_site_query(
    field_name: str, value: Any, warnings: _WarningBuilder, path: str
) -> None:
    if field_name != "q" or not isinstance(value, str):
        return
    if SITE_QUERY_PATTERN.search(value):
        warnings.add(f'use "domains" instead of site: syntax in "{path}"')


def _warn_unused_model_fields(
    model: type[BaseModel],
    data: Mapping[Any, Any],
    used_keys: set[Any],
    warnings: _WarningBuilder,
    path: str,
) -> None:
    lookup = field_lookup(model)
    for key in data:
        if key in used_keys:
            continue
        rendered_path = field_path(path, key)
        if not isinstance(key, str):
            warnings.add(f'ignored unrecognized field "{rendered_path}"')
            continue
        if lookup.get(key.lower()) is None:
            warnings.add(f'ignored unrecognized field "{rendered_path}"')
        else:
            warnings.add(f'ignored duplicate field "{rendered_path}"')
