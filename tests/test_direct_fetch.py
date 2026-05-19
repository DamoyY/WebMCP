from __future__ import annotations
from web_mcp.config import DirectFetchConfig
from web_mcp.direct_fetch import resolve_direct_fetch_target


def _config() -> DirectFetchConfig:
    return DirectFetchConfig(
        max_bytes=1000,
        github_hosts=[
            "github.com",
            "raw.githubusercontent.com",
            "gist.githubusercontent.com",
        ],
        gitlab_hosts=["gitlab.com"],
        bitbucket_hosts=["bitbucket.org"],
        text_file_extensions=[".py", ".md", ".txt"],
        text_file_names=["Dockerfile", "README"],
    )


def test_github_blob_text_file_resolves_to_raw_url() -> None:
    target = resolve_direct_fetch_target(
        "https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md",
        _config(),
    )
    assert target is not None
    assert (
        target.raw_url
        == "https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md"
    )


def test_github_non_text_file_is_not_direct_fetched() -> None:
    target = resolve_direct_fetch_target(
        "https://github.com/example/repo/blob/main/assets/logo.png", _config()
    )
    assert target is None
