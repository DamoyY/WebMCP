from __future__ import annotations
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator

SearchCategory = Literal[
    "company",
    "research paper",
    "news",
    "pdf",
    "personal site",
    "financial report",
    "people",
]


class SearchQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(min_length=1)
    recency: int | None = Field(default=None, ge=1)
    domains: list[str] | None = None
    category: SearchCategory | None = None


class SearchResult(BaseModel):
    title: str | None
    date: str | None
    url: str
    summary: str


class SearchQueryResponse(BaseModel):
    results: list[SearchResult]
    warning: list[str] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class SearchQueryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requests: list[SearchQueryRequest]


class OpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    chunk: int = Field(default=1, ge=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be an absolute HTTP or HTTPS URL")
        return value


class OpenPage(BaseModel):
    chunk: int
    total_chunks: int
    content: str


class OpenResponse(BaseModel):
    pages: list[OpenPage]
    warning: list[str] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class OpenArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requests: list[OpenRequest]


class FindRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    pattern: str = Field(min_length=1)
    snippet_tokens: int | None = Field(default=None, ge=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return OpenRequest(url=value).url


class FindMatch(BaseModel):
    chunk: int
    snippet: str


class FindPage(BaseModel):
    total_chunks: int
    matches: list[FindMatch]


class FindResponse(BaseModel):
    pages: list[FindPage]
    warning: list[str] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class FindArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requests: list[FindRequest]
