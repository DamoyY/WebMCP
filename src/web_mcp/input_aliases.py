from __future__ import annotations
import json
from collections.abc import Mapping
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin
from pydantic import BaseModel


def matching_key(
    model: type[BaseModel], data: Mapping[Any, Any], field_name: str
) -> str | None:
    if field_name in data:
        return field_name
    lookup = field_lookup(model)
    for key in data:
        if isinstance(key, str) and lookup.get(key.lower()) == field_name:
            return key
    return None


def field_path(path: str, key: Any) -> str:
    rendered_key = str(key)
    return f"{path}.{rendered_key}" if path else rendered_key


def looks_like_model(model: type[BaseModel], data: Mapping[Any, Any]) -> bool:
    lookup = field_lookup(model)
    return any(isinstance(key, str) and key.lower() in lookup for key in data)


def request_model(arguments_model: type[BaseModel]) -> type[BaseModel]:
    item_type = list_item_type(arguments_model.model_fields["requests"].annotation)
    model = model_type(item_type)
    if model is None:
        raise TypeError("requests must be a list of Pydantic models")
    return model


def field_lookup(model: type[BaseModel]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field_name in model.model_fields:
        for alias in name_aliases(field_name):
            lookup[alias.lower()] = field_name
    return lookup


def name_aliases(name: str) -> set[str]:
    aliases = {name, singularize(name), pluralize(name)}
    if name == "q":
        aliases.update({"query", "queries"})
    return aliases


def singularize(name: str) -> str:
    parts = name.split("_")
    parts[-1] = singularize_word(parts[-1])
    return "_".join(parts)


def pluralize(name: str) -> str:
    parts = name.split("_")
    parts[-1] = pluralize_word(parts[-1])
    return "_".join(parts)


def singularize_word(word: str) -> str:
    if word.endswith("ies") and len(word) > 3:
        return f"{word[:-3]}y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def pluralize_word(word: str) -> str:
    if word.endswith("y") and (len(word) == 1 or word[-2] not in "aeiou"):
        return f"{word[:-1]}ies"
    if word.endswith("s"):
        return word
    return f"{word}s"


def list_item_type(annotation: Any) -> Any | None:
    for option in annotation_options(annotation):
        if get_origin(option) is list:
            args = get_args(option)
            return args[0] if args else Any
    return None


def model_type(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for option in annotation_options(annotation):
        if isinstance(option, type) and issubclass(option, BaseModel):
            return option
    return None


def literal_string_values(annotation: Any) -> list[str]:
    literals: list[str] = []
    for option in annotation_options(annotation):
        if get_origin(option) is Literal:
            literals.extend(arg for arg in get_args(option) if isinstance(arg, str))
    return literals


def annotation_options(annotation: Any) -> tuple[Any, ...]:
    origin = get_origin(annotation)
    if origin in {UnionType, Union}:
        return get_args(annotation)
    if isinstance(annotation, UnionType):
        return get_args(annotation)
    return (annotation,)


def parse_json_container(value: Any) -> Any:
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
