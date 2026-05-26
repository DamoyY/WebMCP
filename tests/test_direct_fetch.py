from __future__ import annotations
from config import DirectFetchConfig
from direct_fetch import resolve_direct_fetch_target


def _config() -> DirectFetchConfig:
    return DirectFetchConfig(
        max_bytes=1000,
        github_hosts=[
            "github.com",
            "raw.githubusercontent.com",
            "gist.githubusercontent.com",
        ],
        huggingface_hosts=["huggingface.co"],
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


def test_huggingface_blob_text_file_resolves_to_raw_url() -> None:
    target = resolve_direct_fetch_target(
        "https://huggingface.co/openai/whisper-tiny/blob/main/README.md", _config()
    )
    assert target is not None
    assert (
        target.raw_url
        == "https://huggingface.co/openai/whisper-tiny/resolve/main/README.md"
    )


def test_huggingface_root_model_text_file_resolves_to_raw_url() -> None:
    target = resolve_direct_fetch_target(
        "https://huggingface.co/gpt2/blob/main/README.md", _config()
    )
    assert target is not None
    assert target.raw_url == "https://huggingface.co/gpt2/resolve/main/README.md"


def test_huggingface_non_text_file_is_not_direct_fetched() -> None:
    target = resolve_direct_fetch_target(
        "https://huggingface.co/openai/whisper-tiny/blob/main/model.safetensors",
        _config(),
    )
    assert target is None


def test_wikipedia_page_resolves_to_raw_wikitext_url() -> None:
    target = resolve_direct_fetch_target(
        "https://en.wikipedia.org/wiki/Pet_door", _config()
    )
    assert target is not None
    assert (
        target.raw_url
        == "https://en.wikipedia.org/w/index.php?title=Pet_door&action=raw"
    )


def test_wikipedia_non_ascii_page_title_is_encoded_for_raw_url() -> None:
    target = resolve_direct_fetch_target(
        "https://zh.wikipedia.org/wiki/北京", _config()
    )
    assert target is not None
    assert (
        target.raw_url
        == "https://zh.wikipedia.org/w/index.php?title=%E5%8C%97%E4%BA%AC&action=raw"
    )
