from __future__ import annotations
from web_mcp.chunking import TokenChunker
from web_mcp.config import ChunkingConfig


def test_split_uses_overlap() -> None:
    chunker = TokenChunker(
        ChunkingConfig(tokenizer="cl100k_base", chunk_tokens=10, overlap_ratio=0.2)
    )
    text = " ".join(f"word{i}" for i in range(40))
    chunks = chunker.split(text)
    assert len(chunks) > 1
    assert chunks[0].index == 1
    assert chunks[1].index == 2
    assert chunker.count_tokens(chunks[0].content) <= 10


def test_select_rejects_out_of_range_chunk() -> None:
    chunker = TokenChunker(
        ChunkingConfig(tokenizer="cl100k_base", chunk_tokens=100, overlap_ratio=0.1)
    )
    try:
        chunker.select("short text", 2)
    except ValueError as error:
        assert "out of range" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_snippet_around_span_limits_token_count() -> None:
    chunker = TokenChunker(
        ChunkingConfig(tokenizer="cl100k_base", chunk_tokens=100, overlap_ratio=0.1)
    )
    text = "alpha beta gamma delta epsilon"
    snippet = chunker.snippet_around_span(text, 6, 10, 3)
    assert "beta" in snippet
    assert chunker.count_tokens(snippet) <= 3
