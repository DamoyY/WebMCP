from __future__ import annotations
from dataclasses import dataclass
import tiktoken
from web_mcp.config import ChunkingConfig


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str


class TokenChunker:
    def __init__(self, config: ChunkingConfig) -> None:
        self._encoding = tiktoken.get_encoding(config.tokenizer)
        self._chunk_tokens = config.chunk_tokens
        self._overlap_tokens = int(config.chunk_tokens * config.overlap_ratio)

    def count_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def snippet_around_span(
        self, text: str, start: int, end: int, max_tokens: int
    ) -> str:
        before_tokens = self._encoding.encode(text[:start])
        match_tokens = self._encoding.encode(text[start:end])
        after_tokens = self._encoding.encode(text[end:])
        if len(match_tokens) >= max_tokens:
            return self._encoding.decode(match_tokens[:max_tokens])
        remaining = max_tokens - len(match_tokens)
        left_count = min(len(before_tokens), remaining // 2)
        right_count = min(len(after_tokens), remaining - left_count)
        unused = remaining - left_count - right_count
        if unused > 0:
            extra_left = min(len(before_tokens) - left_count, unused)
            left_count += extra_left
            unused -= extra_left
            right_count += min(len(after_tokens) - right_count, unused)
        selected_tokens = _tail(before_tokens, left_count) + match_tokens
        selected_tokens += after_tokens[:right_count]
        return self._encoding.decode(selected_tokens)

    def split(self, text: str) -> list[TextChunk]:
        tokens = self._encoding.encode(text)
        if len(tokens) <= self._chunk_tokens:
            return [TextChunk(index=1, content=text)]
        chunks: list[TextChunk] = []
        step = max(1, self._chunk_tokens - self._overlap_tokens)
        start = 0
        while start < len(tokens):
            end = min(len(tokens), start + self._chunk_tokens)
            chunks.append(
                TextChunk(
                    index=len(chunks) + 1,
                    content=self._encoding.decode(tokens[start:end]),
                )
            )
            if end == len(tokens):
                break
            start += step
        return chunks

    def select(self, text: str, chunk_index: int) -> tuple[TextChunk, int, int]:
        chunks = self.split(text)
        if chunk_index > len(chunks):
            raise ValueError(
                f"chunk {chunk_index} is out of range; total chunks: {len(chunks)}"
            )
        return chunks[chunk_index - 1], len(chunks), self.count_tokens(text)


def _tail(items: list[int], count: int) -> list[int]:
    if count == 0:
        return []
    return items[-count:]
