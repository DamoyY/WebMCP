from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote, urlparse


@dataclass(frozen=True)
class PackageRegistryTarget:
    request_url: str
    json_fields_last: tuple[str, ...]


def resolve_package_registry_target(url: str) -> PackageRegistryTarget | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]

    if host == "pypi.org" and (name := _pypi_package_name(parts)) is not None:
        return PackageRegistryTarget(
            request_url=f"https://pypi.org/pypi/{quote(name, safe='')}/json",
            json_fields_last=("releases",),
        )
    if (
        host in {"npmjs.com", "www.npmjs.com", "registry.npmjs.org"}
        and (name := _npm_package_name(host, parts)) is not None
    ):
        return PackageRegistryTarget(
            request_url=f"https://registry.npmjs.org/{quote(name, safe='@')}",
            json_fields_last=("versions",),
        )
    if host == "crates.io" and (name := _crates_package_name(parts)) is not None:
        return PackageRegistryTarget(
            request_url=f"https://crates.io/api/v1/crates/{quote(name, safe='')}",
            json_fields_last=("versions",),
        )
    return None


def format_package_registry_json(payload: Any, fields_last: tuple[str, ...]) -> str:
    if isinstance(payload, dict):
        reordered = {
            key: value for key, value in payload.items() if key not in fields_last
        }
        reordered.update(
            (field, payload[field]) for field in fields_last if field in payload
        )
        payload = reordered
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _pypi_package_name(parts: list[str]) -> str | None:
    if len(parts) >= 2 and parts[0] == "project":
        return _unquoted_segment(parts[1])
    if len(parts) == 3 and parts[0] == "pypi" and parts[2] == "json":
        return _unquoted_segment(parts[1])
    return None


def _npm_package_name(host: str, parts: list[str]) -> str | None:
    if host in {"npmjs.com", "www.npmjs.com"}:
        if not parts or parts[0] != "package":
            return None
        parts = parts[1:]
    decoded = [unquote(part) for part in parts]
    if len(decoded) == 1:
        name_parts = decoded[0].split("/")
    else:
        name_parts = decoded
    if len(name_parts) == 1 and _is_segment(name_parts[0]):
        return name_parts[0]
    if (
        len(name_parts) == 2
        and name_parts[0].startswith("@")
        and _is_segment(name_parts[0][1:])
        and _is_segment(name_parts[1])
    ):
        return "/".join(name_parts)
    return None


def _crates_package_name(parts: list[str]) -> str | None:
    if len(parts) >= 2 and parts[0] == "crates":
        return _unquoted_segment(parts[1])
    if len(parts) == 4 and parts[:3] == ["api", "v1", "crates"]:
        return _unquoted_segment(parts[3])
    return None


def _unquoted_segment(value: str) -> str | None:
    decoded = unquote(value)
    return decoded if _is_segment(decoded) else None


def _is_segment(value: str) -> bool:
    return bool(value) and "/" not in value
