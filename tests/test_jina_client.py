from __future__ import annotations
import json
import httpx
import pytest
import respx
from config import HttpConfig, JinaConfig, JinaViewportConfig
from jina_client import JinaReaderClient, _extract_content


def test_extract_content_from_jina_data_payload() -> None:
    response = httpx.Response(200, json={"data": {"content": "# Title\nBody"}})
    assert _extract_content(response) == "# Title\nBody"


def test_extract_content_from_jina_event_stream_payloads() -> None:
    response = httpx.Response(
        200,
        headers={"Content-Type": "text/event-stream"},
        text='data: {"data": {"content": "# Title\\n"}}\n\n'
        'data: {"content": "Body"}\n\n'
        "data: [DONE]\n\n",
    )
    assert _extract_content(response) == "# Title\nBody"


@pytest.mark.asyncio
async def test_read_markdown_sends_reader_request_headers_and_viewport() -> None:
    client = JinaReaderClient(_jina_config(), _http_config())
    with respx.mock(assert_all_called=True) as router:
        route = router.post("https://r.jina.ai/").mock(
            return_value=httpx.Response(200, text="# Title")
        )
        markdown = await client.read_markdown("https://www.example.com", "secret")
    request = route.calls[0].request
    assert markdown == "# Title"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["Accept"] == "text/event-stream"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["X-Engine"] == "cf-browser-rendering"
    assert request.headers["X-Locale"] == "en-US"
    assert request.headers["X-No-Cache"] == "true"
    assert request.headers["X-Respond-With"] == "readerlm-v2"
    assert request.headers["X-Retain-Images"] == "none"
    assert request.headers["X-Return-Format"] == "markdown"
    assert request.headers["X-With-Shadow-Dom"] == "true"
    assert json.loads(request.content) == {
        "url": "https://www.example.com",
        "viewport": {"width": 1920, "height": 1080},
    }


def _jina_config() -> JinaConfig:
    return JinaConfig(
        endpoint="https://r.jina.ai/",
        accept="text/event-stream",
        return_format="markdown",
        engine="cf-browser-rendering",
        locale="en-US",
        no_cache=True,
        respond_with="readerlm-v2",
        retain_images="none",
        with_shadow_dom=True,
        viewport=JinaViewportConfig(width=1920, height=1080),
    )


def _http_config() -> HttpConfig:
    return HttpConfig(timeout_seconds=45.0, direct_fetch_timeout_seconds=20.0)
