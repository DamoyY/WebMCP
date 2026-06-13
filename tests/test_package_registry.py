from __future__ import annotations

import json

import httpx
import pytest
import respx

from web_mcp.config import DirectFetchConfig, HttpConfig
from web_mcp.direct_fetch import fetch_direct_text, resolve_direct_fetch_target
from web_mcp.errors import ClientFacingError


@pytest.mark.parametrize(
    ("url", "request_url", "field_last"),
    [
        (
            "https://pypi.org/project/httpx/",
            "https://pypi.org/pypi/httpx/json",
            "releases",
        ),
        (
            "https://www.npmjs.com/package/react",
            "https://registry.npmjs.org/react",
            "versions",
        ),
        (
            "https://www.npmjs.com/package/@types/node",
            "https://registry.npmjs.org/@types%2Fnode",
            "versions",
        ),
        (
            "https://crates.io/crates/serde",
            "https://crates.io/api/v1/crates/serde",
            "versions",
        ),
    ],
)
def test_package_page_resolves_to_registry_json(
    url: str, request_url: str, field_last: str
) -> None:
    target = resolve_direct_fetch_target(url, _direct_config())
    assert target is not None
    assert target.request_url == request_url
    assert target.response_format == "package_registry_json"
    assert target.json_fields_last == (field_last,)


@pytest.mark.asyncio
async def test_package_registry_json_is_formatted_with_large_field_last() -> None:
    target = resolve_direct_fetch_target(
        "https://pypi.org/project/example/", _direct_config()
    )
    assert target is not None
    payload = {
        "releases": {"1.0.0": [{"filename": "example.whl"}]},
        "info": {"name": "example", "summary": "示例"},
        "urls": [],
    }
    with respx.mock(assert_all_called=True) as router:
        route = router.get(target.request_url).mock(
            return_value=httpx.Response(200, json=payload)
        )
        content = await fetch_direct_text(target, _direct_config(), _http_config())

    expected = json.dumps(
        {"info": payload["info"], "urls": [], "releases": payload["releases"]},
        ensure_ascii=False,
        indent=2,
    )
    assert content == expected
    assert route.calls[0].request.headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_package_registry_rejects_malformed_json() -> None:
    target = resolve_direct_fetch_target(
        "https://crates.io/crates/serde", _direct_config()
    )
    assert target is not None
    with respx.mock(assert_all_called=True) as router:
        router.get(target.request_url).mock(return_value=httpx.Response(200, text="{"))
        with pytest.raises(
            ClientFacingError, match="Package registry returned malformed JSON"
        ):
            await fetch_direct_text(target, _direct_config(), _http_config())


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
