from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from web_mcp import page_fetcher
from web_mcp.config import AppConfig, DirectFetchConfig, HttpConfig
from web_mcp.errors import ClientFacingError
from web_mcp.page_fetcher import PageFetcher


@pytest.mark.asyncio
async def test_microsoft_learn_uses_direct_markdown_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetcher = _fetcher()
    direct_fetch = AsyncMock(return_value="# From Microsoft Learn")
    jina_fetch = AsyncMock(return_value="# From Jina")
    monkeypatch.setattr(page_fetcher, "fetch_direct_text", direct_fetch)
    monkeypatch.setattr(fetcher._jina, "read_markdown", jina_fetch)

    content = await fetcher.fetch(
        "https://learn.microsoft.com/en-us/dotnet/", "jina-secret"
    )

    await_args = direct_fetch.await_args
    assert await_args is not None
    target = await_args.args[0]
    assert target.request_url == (
        "https://learn.microsoft.com/en-us/dotnet/?accept=text%2Fmarkdown"
    )
    assert content.source == "direct"
    assert content.markdown == "# From Microsoft Learn"
    jina_fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_microsoft_learn_direct_failure_falls_back_to_jina(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetcher = _fetcher()
    direct_fetch = AsyncMock(side_effect=ClientFacingError("direct fetch failed"))
    jina_fetch = AsyncMock(return_value="# From Jina")
    monkeypatch.setattr(page_fetcher, "fetch_direct_text", direct_fetch)
    monkeypatch.setattr(fetcher._jina, "read_markdown", jina_fetch)

    content = await fetcher.fetch(
        "https://learn.microsoft.com/en-us/dotnet/", "jina-secret"
    )

    assert content.source == "jina"
    assert content.markdown == "# From Jina"
    jina_fetch.assert_awaited_once_with(
        "https://learn.microsoft.com/en-us/dotnet/", "jina-secret"
    )


@pytest.mark.asyncio
async def test_other_direct_failure_does_not_fall_back_to_jina(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetcher = _fetcher()
    direct_fetch = AsyncMock(side_effect=ClientFacingError("direct fetch failed"))
    jina_fetch = AsyncMock(return_value="# From Jina")
    monkeypatch.setattr(page_fetcher, "fetch_direct_text", direct_fetch)
    monkeypatch.setattr(fetcher._jina, "read_markdown", jina_fetch)

    with pytest.raises(ClientFacingError, match="direct fetch failed"):
        await fetcher.fetch(
            "https://github.com/example/repo/blob/main/README.md", "jina-secret"
        )

    jina_fetch.assert_not_awaited()


def _fetcher() -> PageFetcher:
    config = MagicMock(spec=AppConfig)
    config.direct_fetch = DirectFetchConfig(
        max_bytes=1000,
        github_hosts=["github.com"],
        huggingface_hosts=[],
        gitlab_hosts=[],
        bitbucket_hosts=[],
        text_file_extensions=[".md"],
        text_file_names=[],
    )
    config.http = HttpConfig(timeout_seconds=45.0, direct_fetch_timeout_seconds=20.0)
    config.jina = MagicMock()
    config.headers = MagicMock()
    config.headers.jina_api_key = "x-jina-api-key"
    return PageFetcher(config)
