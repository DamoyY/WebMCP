from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from .chunking import TokenChunker
from .models import OpenPage
from .page_fetcher import PageContent

FIRST_CHUNK_INDEX = 1


def normalize_open_chunk_requests(raw_requests: Any, warnings: list[str]) -> Any:
    if not isinstance(raw_requests, list):
        return raw_requests
    normalized_requests: list[Any] = []
    for index, request in enumerate(raw_requests):
        if not isinstance(request, Mapping):
            normalized_requests.append(request)
            continue
        normalized_request = dict(request)
        if "chunk" not in normalized_request:
            normalized_request["chunk"] = FIRST_CHUNK_INDEX
            warnings.append(
                f'"requests[{index}].chunk" is required; using {FIRST_CHUNK_INDEX}'
            )
        elif _is_empty_chunk(normalized_request["chunk"]):
            normalized_request["chunk"] = FIRST_CHUNK_INDEX
            warnings.append(
                f'"requests[{index}].chunk" is empty; using {FIRST_CHUNK_INDEX}'
            )
        else:
            chunk = _integer_value(normalized_request["chunk"])
            if chunk is not None and chunk < FIRST_CHUNK_INDEX:
                normalized_request["chunk"] = FIRST_CHUNK_INDEX
                warnings.append(
                    f'"requests[{index}].chunk" must be greater than or equal to '
                    f"{FIRST_CHUNK_INDEX}; using {FIRST_CHUNK_INDEX}"
                )
        normalized_requests.append(normalized_request)
    return normalized_requests


def open_page_chunk(
    page: PageContent,
    chunk_index: int,
    request_index: int,
    chunker: TokenChunker,
    warnings: list[str],
) -> OpenPage:
    chunks = chunker.split(page.markdown)
    if chunk_index < FIRST_CHUNK_INDEX or chunk_index > len(chunks):
        warnings.append(
            f'"requests[{request_index}].chunk" must be between '
            f"{FIRST_CHUNK_INDEX} and {len(chunks)}; using {FIRST_CHUNK_INDEX}"
        )
        selected = chunks[0]
    else:
        selected = chunks[chunk_index - FIRST_CHUNK_INDEX]
    return OpenPage(
        chunk=selected.index, total_chunks=len(chunks), content=selected.content
    )


def _is_empty_chunk(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, Mapping):
        return not value
    if isinstance(value, (list, tuple, set)):
        return not value
    return False


def _integer_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None
