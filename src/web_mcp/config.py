from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    instructions: str
    host: str
    port: int
    log_level: LogLevel
    streamable_http_path: str
    stateless_http: bool
    json_response: bool
    health_path: str

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()


class HeaderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exa_api_key: str
    jina_api_key: str


class SearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    num_results: PositiveInt
    type: str
    highlights_max_characters: PositiveInt
    max_age_hours: int = 24
    livecrawl_timeout: PositiveInt = 30000


class HttpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout_seconds: float = Field(gt=0)
    direct_fetch_timeout_seconds: float = Field(gt=0)


class JinaViewportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: PositiveInt
    height: PositiveInt


class JinaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    accept: str
    return_format: str
    engine: str
    locale: str
    no_cache: bool
    respond_with: str
    retain_images: str
    with_shadow_dom: bool
    viewport: JinaViewportConfig


class ChunkingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tokenizer: str
    chunk_tokens: PositiveInt
    overlap_ratio: float = Field(ge=0, lt=1)


class FindConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_snippet_tokens: PositiveInt
    max_matches_per_page: PositiveInt


class DirectFetchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_bytes: PositiveInt
    github_hosts: list[str]
    huggingface_hosts: list[str]
    gitlab_hosts: list[str]
    bitbucket_hosts: list[str]
    text_file_extensions: list[str]
    text_file_names: list[str]


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server: ServerConfig
    headers: HeaderConfig
    search: SearchConfig
    http: HttpConfig
    jina: JinaConfig
    chunking: ChunkingConfig
    find: FindConfig
    direct_fetch: DirectFetchConfig


def config_path() -> Path:
    configured = os.environ.get("WEB_MCP_CONFIG")
    if configured:
        return Path(configured)
    return Path.cwd() / "config" / "default.yaml"


@lru_cache
def load_config() -> AppConfig:
    path = config_path()
    with path.open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)
    return AppConfig.model_validate(data)
