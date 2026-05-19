from __future__ import annotations
from web_mcp.exa_client import _normalize_domains


def test_normalize_domains_accepts_list_and_comma_string() -> None:
    assert _normalize_domains(["https://OpenAI.com/docs", "example.com"]) == [
        "openai.com",
        "example.com",
    ]
    assert _normalize_domains("openai.com, example.org docs.example.net") == [
        "openai.com",
        "example.org",
        "docs.example.net",
    ]
