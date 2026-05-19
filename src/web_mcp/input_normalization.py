from __future__ import annotations
import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin
from pydantic import BaseModel

WARNING_PREFIX = "Input parameters were normalized: "


@dataclass(frozen=True)
class NormalizationResult:
    requests: Any
    warning: str | None


def normalize_tool_arguments(
    arguments_model: type[BaseModel], raw_arguments: Any
) -> NormalizationResult:
    warnings = _WarningBuilder()
    data = _parse_json_container(raw_arguments)
    if isinstance(data, Mapping):
        requests_key = _matching_key(arguments_model, data, "requests")
        if requests_key is not None:
            if requests_key != "requests":
                warnings.add(f'use "requests" instead of "{requests_key}"')
            normalized_requests = _normalize_model_field(
                arguments_model, "requests", data[requests_key], warnings, "requests"
            )
            return NormalizationResult(
                requests=normalized_requests, warning=warnings.message()
            )
        request_model = _request_model(arguments_model)
        if _looks_like_model(request_model, data):
            warnings.add('wrap the request object in the "requests" array')
            normalized_request = _normalize_model_value(
                request_model, data, warnings, "request"
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

    def message(self) -> str | None:
        if not self._messages:
            return None
        return f"{WARNING_PREFIX}{'; '.join(self._messages)}."


def _normalize_model_value(
    model: type[BaseModel], raw_value: Any, warnings: _WarningBuilder, path: str
) -> Any:
    value = _parse_json_container(raw_value)
    if not isinstance(value, Mapping):
        return value
    lookup = _field_lookup(model)
    normalized: dict[Any, Any] = {}
    for raw_key, raw_item in value.items():
        if not isinstance(raw_key, str):
            normalized[raw_key] = raw_item
            continue
        canonical = lookup.get(raw_key.lower())
        if canonical is None:
            normalized[raw_key] = raw_item
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
    item_type = _list_item_type(field.annotation)
    value = _parse_json_container(raw_value)
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
    model = _model_type(annotation)
    if model is not None:
        return _normalize_model_value(model, raw_value, warnings, path)
    value = _normalize_url(field_name, raw_value, warnings, path)
    return _normalize_literal(annotation, value, warnings, path)


def _normalize_url(
    field_name: str, value: Any, warnings: _WarningBuilder, path: str
) -> Any:
    if not isinstance(value, str) or _singularize(field_name).lower() != "url":
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
    literals = _literal_string_values(annotation)
    if not literals:
        return value
    lookup: dict[str, str] = {}
    for literal in literals:
        for alias in _name_aliases(literal):
            lookup[alias.lower()] = literal
    normalized = lookup.get(value.strip().lower())
    if normalized is None:
        return value
    if normalized != value:
        warnings.add(f'use "{normalized}" instead of "{value}" for "{path}"')
    return normalized


def _matching_key(
    model: type[BaseModel], data: Mapping[Any, Any], field_name: str
) -> str | None:
    lookup = _field_lookup(model)
    for key in data:
        if isinstance(key, str) and lookup.get(key.lower()) == field_name:
            return key
    return None


def _looks_like_model(model: type[BaseModel], data: Mapping[Any, Any]) -> bool:
    lookup = _field_lookup(model)
    return any(isinstance(key, str) and key.lower() in lookup for key in data)


def _request_model(arguments_model: type[BaseModel]) -> type[BaseModel]:
    item_type = _list_item_type(arguments_model.model_fields["requests"].annotation)
    model = _model_type(item_type)
    if model is None:
        raise TypeError("requests must be a list of Pydantic models")
    return model


def _field_lookup(model: type[BaseModel]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field_name in model.model_fields:
        for alias in _name_aliases(field_name):
            lookup[alias.lower()] = field_name
    return lookup


def _name_aliases(name: str) -> set[str]:
    aliases = {name, _singularize(name), _pluralize(name)}
    if name == "q":
        aliases.update({"query", "queries"})
    return aliases


def _singularize(name: str) -> str:
    parts = name.split("_")
    parts[-1] = _singularize_word(parts[-1])
    return "_".join(parts)


def _pluralize(name: str) -> str:
    parts = name.split("_")
    parts[-1] = _pluralize_word(parts[-1])
    return "_".join(parts)


def _singularize_word(word: str) -> str:
    if word.endswith("ies") and len(word) > 3:
        return f"{word[:-3]}y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def _pluralize_word(word: str) -> str:
    if word.endswith("y") and (len(word) == 1 or word[-2] not in "aeiou"):
        return f"{word[:-1]}ies"
    if word.endswith("s"):
        return word
    return f"{word}s"


def _list_item_type(annotation: Any) -> Any | None:
    for option in _annotation_options(annotation):
        if get_origin(option) is list:
            args = get_args(option)
            return args[0] if args else Any
    return None


def _model_type(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for option in _annotation_options(annotation):
        if isinstance(option, type) and issubclass(option, BaseModel):
            return option
    return None


def _literal_string_values(annotation: Any) -> list[str]:
    literals: list[str] = []
    for option in _annotation_options(annotation):
        if get_origin(option) is Literal:
            literals.extend(arg for arg in get_args(option) if isinstance(arg, str))
    return literals


def _annotation_options(annotation: Any) -> tuple[Any, ...]:
    origin = get_origin(annotation)
    if origin in {UnionType, Union}:
        return get_args(annotation)
    if isinstance(annotation, UnionType):
        return get_args(annotation)
    return (annotation,)


def _parse_json_container(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped.startswith(("{", "[")):
        return value
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return value
    return parsed if isinstance(parsed, (dict, list)) else value
