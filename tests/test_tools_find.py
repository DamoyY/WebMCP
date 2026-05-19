from __future__ import annotations
import re
from web_mcp.chunking import TokenChunker
from web_mcp.config import ChunkingConfig, FindConfig
from web_mcp.models import FindPage
from web_mcp.page_fetcher import PageContent
from web_mcp.tools import _find_in_page


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
