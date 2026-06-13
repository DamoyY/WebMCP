from __future__ import annotations
from web_mcp.chunking import TokenChunker
from web_mcp.config import ChunkingConfig
from web_mcp.models import OpenArguments
from web_mcp.open_chunks import normalize_open_chunk_requests, open_page_chunk
from web_mcp.page_fetcher import PageContent


def test_open_chunk_is_required_in_schema() -> None:
    schema = OpenArguments.model_json_schema()
    request_schema = schema["$defs"]["OpenRequest"]
    assert "chunk" in request_schema["required"]


def test_empty_open_chunk_uses_first_chunk_with_warning() -> None:
    warnings: list[str] = []
    requests = normalize_open_chunk_requests(
        [{"url": "https://example.com", "chunk": ""}], warnings
    )
    assert requests == [{"url": "https://example.com", "chunk": 1}]
    assert warnings == ['"requests[0].chunk" is empty; using 1']


def test_missing_open_chunk_uses_first_chunk_with_warning() -> None:
    warnings: list[str] = []
    requests = normalize_open_chunk_requests([{"url": "https://example.com"}], warnings)
    assert requests == [{"url": "https://example.com", "chunk": 1}]
    assert warnings == ['"requests[0].chunk" is required; using 1']


def test_lower_out_of_range_open_chunk_uses_first_chunk_with_warning() -> None:
    warnings: list[str] = []
    requests = normalize_open_chunk_requests(
        [{"url": "https://example.com", "chunk": 0}], warnings
    )
    assert requests == [{"url": "https://example.com", "chunk": 1}]
    assert warnings == [
        '"requests[0].chunk" must be greater than or equal to 1; using 1'
    ]


def test_out_of_range_open_chunk_returns_first_chunk_with_warning() -> None:
    warnings: list[str] = []
    page = PageContent(
        url="https://example.com", source="jina", markdown="alpha beta gamma"
    )
    result = open_page_chunk(page, 2, 0, _chunker(), warnings)
    assert result.model_dump() == {
        "chunk": 1,
        "total_chunks": 1,
        "content": "alpha beta gamma",
    }
    assert warnings == ['"requests[0].chunk" must be between 1 and 1; using 1']


def _chunker() -> TokenChunker:
    return TokenChunker(
        ChunkingConfig(tokenizer="o200k_base", chunk_tokens=100, overlap_ratio=0.1)
    )
