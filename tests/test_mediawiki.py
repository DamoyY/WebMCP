from __future__ import annotations

from urllib.parse import ParseResult, parse_qs, urlparse

import httpx
import pytest
import respx

from web_mcp.config import DirectFetchConfig, HttpConfig
from web_mcp.direct_fetch import (
    DirectFetchTarget,
    fetch_direct_text,
    resolve_direct_fetch_target,
)
from web_mcp.errors import ClientFacingError
from web_mcp.mediawiki import extract_mediawiki_content, resolve_mediawiki_api_url


@pytest.mark.parametrize(
    ("url", "api_host", "title"),
    [
        ("https://en.wiktionary.org/wiki/test", "en.wiktionary.org", "test"),
        (
            "https://commons.wikimedia.org/wiki/File:Example.jpg",
            "commons.wikimedia.org",
            "File:Example.jpg",
        ),
        (
            "https://www.mediawiki.org/wiki/Manual:FAQ",
            "www.mediawiki.org",
            "Manual:FAQ",
        ),
        ("https://www.wikidata.org/wiki/Q42", "www.wikidata.org", "Q42"),
        ("https://www.wikifunctions.org/wiki/Z1", "www.wikifunctions.org", "Z1"),
    ],
)
def test_wikimedia_family_page_resolves_to_revision_api(
    url: str, api_host: str, title: str
) -> None:
    parsed, query = _resolved_api(url)
    assert parsed.netloc == api_host
    assert parsed.path == "/w/api.php"
    assert query["titles"] == [title]
    assert query["redirects"] == ["1"]


def test_fandom_page_resolves_to_root_revision_api() -> None:
    parsed, query = _resolved_api(
        "https://memory-alpha.fandom.com/wiki/Jean-Luc_Picard"
    )
    assert parsed.netloc == "memory-alpha.fandom.com"
    assert parsed.path == "/api.php"
    assert query["titles"] == ["Jean-Luc_Picard"]


def test_fandom_page_is_selected_for_direct_fetch() -> None:
    target = resolve_direct_fetch_target(
        "https://memory-alpha.fandom.com/wiki/Jean-Luc_Picard", _direct_config()
    )
    assert target is not None
    assert target.response_format == "mediawiki_api"
    assert target.request_url.startswith("https://memory-alpha.fandom.com/api.php?")


def test_localized_fandom_page_resolves_to_localized_revision_api() -> None:
    parsed, query = _resolved_api("https://community.fandom.com/ja/wiki/Help:Bots")
    assert parsed.path == "/ja/api.php"
    assert query["titles"] == ["Help:Bots"]


def test_mediawiki_oldid_uses_revision_selector_without_redirects() -> None:
    _, query = _resolved_api(
        "https://en.wikipedia.org/w/index.php?title=Pet_door&oldid=1276516112"
    )
    assert query["revids"] == ["1276516112"]
    assert "titles" not in query
    assert "redirects" not in query


def test_fandom_curid_uses_page_id_selector() -> None:
    _, query = _resolved_api("https://community.fandom.com/index.php?curid=123")
    assert query["pageids"] == ["123"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.fandom.com/wiki/Example",
        "https://memory-alpha.fandom.com/",
        "https://memory-alpha.fandom.com/f/p/123",
        "https://en.wikipedia.org.example.com/wiki/Example",
        "https://example.com/wiki/Example",
    ],
)
def test_non_mediawiki_page_is_not_resolved(url: str) -> None:
    assert resolve_mediawiki_api_url(url) is None


def test_extract_mediawiki_content_returns_main_revision_content() -> None:
    payload = {
        "query": {
            "pages": [{"revisions": [{"slots": {"main": {"content": "# Wikitext"}}}]}]
        }
    }
    assert extract_mediawiki_content(payload) == "# Wikitext"


def test_extract_mediawiki_content_reports_missing_page() -> None:
    with pytest.raises(ClientFacingError, match="page was not found"):
        extract_mediawiki_content({"query": {"pages": [{"missing": True}]}})


def test_extract_mediawiki_content_reports_api_error_code() -> None:
    with pytest.raises(ClientFacingError, match="badtitle"):
        extract_mediawiki_content({"error": {"code": "badtitle"}})


@pytest.mark.asyncio
async def test_fetch_direct_text_decodes_mediawiki_api_response() -> None:
    target = DirectFetchTarget(
        original_url="https://example.fandom.com/wiki/Page",
        request_url="https://example.fandom.com/api.php?action=query",
        response_format="mediawiki_api",
    )
    payload = {
        "query": {
            "pages": [{"revisions": [{"slots": {"main": {"content": "Page source"}}}]}]
        }
    }
    with respx.mock(assert_all_called=True) as router:
        route = router.get(target.request_url).mock(
            return_value=httpx.Response(200, json=payload)
        )
        content = await fetch_direct_text(target, _direct_config(), _http_config())
    assert content == "Page source"
    assert route.calls[0].request.headers["Accept"] == "application/json"
    assert route.calls[0].request.headers["User-Agent"] == "web-mcp/0.1.0"


@pytest.mark.asyncio
async def test_fetch_direct_text_rejects_malformed_mediawiki_json() -> None:
    target = DirectFetchTarget(
        original_url="https://example.fandom.com/wiki/Page",
        request_url="https://example.fandom.com/api.php?action=query",
        response_format="mediawiki_api",
    )
    with respx.mock(assert_all_called=True) as router:
        router.get(target.request_url).mock(return_value=httpx.Response(200, text="{"))
        with pytest.raises(ClientFacingError, match="malformed JSON"):
            await fetch_direct_text(target, _direct_config(), _http_config())


def _resolved_api(url: str) -> tuple[ParseResult, dict[str, list[str]]]:
    resolved = resolve_mediawiki_api_url(url)
    assert resolved is not None
    parsed = urlparse(resolved)
    return parsed, parse_qs(parsed.query)


def _direct_config() -> DirectFetchConfig:
    return DirectFetchConfig(
        max_bytes=1000,
        github_hosts=[],
        huggingface_hosts=[],
        gitlab_hosts=[],
        bitbucket_hosts=[],
        text_file_extensions=[],
        text_file_names=[],
    )


def _http_config() -> HttpConfig:
    return HttpConfig(timeout_seconds=45.0, direct_fetch_timeout_seconds=20.0)
