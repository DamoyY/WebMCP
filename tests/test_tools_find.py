from __future__ import annotations
import re
from web_mcp.chunking import TokenChunker
from web_mcp.config import ChunkingConfig, FindConfig
from web_mcp.models import FindPage, FindRequest
from web_mcp.page_fetcher import PageContent
from web_mcp.tools import _find_in_page, _snippet_tokens_for_request


class _Config:
    chunking = ChunkingConfig(
        tokenizer="cl100k_base", chunk_tokens=100, overlap_ratio=0.1
    )
    find = FindConfig(default_snippet_tokens=8, max_matches_per_page=10)


def test_find_in_page_returns_chunk_number_and_snippet() -> None:
    page = PageContent(
        url="https://example.com", source="jina", markdown="alpha beta gamma"
    )
    result = _find_in_page(
        page, re.compile(r"beta"), 8, TokenChunker(_Config.chunking), _Config.find
    )
    assert isinstance(result, FindPage)
    assert result.model_dump() == {
        "total_chunks": 1,
        "matches": [{"chunk": 1, "snippet": "alpha beta gamma"}],
    }
    assert result.matches[0].chunk == 1
    assert "beta" in result.matches[0].snippet


def test_snippet_tokens_larger_than_chunk_tokens_is_capped() -> None:
    warnings: list[str] = []
    request = FindRequest(url="https://example.com", pattern="beta", snippet_tokens=200)
    assert _snippet_tokens_for_request(request, 100, 8, 0, warnings) == 100
    assert warnings == [
        '"requests[0].snippet_tokens" exceeds chunk_tokens (100); using 100'
    ]
