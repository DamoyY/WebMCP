from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse
import httpx

from . import __version__
from .config import DirectFetchConfig, HttpConfig
from .errors import ClientFacingError, http_service_error, upstream_timeout
from .mediawiki import extract_mediawiki_content, resolve_mediawiki_api_url


@dataclass(frozen=True)
class DirectFetchTarget:
    original_url: str
    request_url: str
    response_format: Literal["text", "mediawiki_api"] = "text"
    fallback_to_jina_on_error: bool = False


def resolve_direct_fetch_target(
    url: str, config: DirectFetchConfig
) -> DirectFetchTarget | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    response_format: Literal["text", "mediawiki_api"] = "text"
    fallback_to_jina_on_error = False
    if (parsed.hostname or "").lower() == "learn.microsoft.com":
        request_url = _microsoft_learn_markdown_url(url)
        fallback_to_jina_on_error = True
    elif host in config.github_hosts:
        request_url = _github_raw_url(url, host, config)
    elif host in config.huggingface_hosts:
        request_url = _huggingface_raw_url(url, host, config)
    elif host in config.gitlab_hosts:
        request_url = _gitlab_raw_url(url, host, config)
    elif host in config.bitbucket_hosts:
        request_url = _bitbucket_raw_url(url, host, config)
    elif mediawiki_url := resolve_mediawiki_api_url(url):
        request_url = mediawiki_url
        response_format = "mediawiki_api"
    else:
        request_url = None
    if request_url is None:
        return None
    return DirectFetchTarget(
        original_url=url,
        request_url=request_url,
        response_format=response_format,
        fallback_to_jina_on_error=fallback_to_jina_on_error,
    )


async def fetch_direct_text(
    target: DirectFetchTarget, direct_config: DirectFetchConfig, http_config: HttpConfig
) -> str:
    headers = {
        "Accept": (
            "application/json"
            if target.response_format == "mediawiki_api"
            else "text/plain,*/*"
        ),
        "Range": f"bytes=0-{direct_config.max_bytes}",
        "User-Agent": f"web-mcp/{__version__}",
    }
    timeout = httpx.Timeout(http_config.direct_fetch_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(target.request_url, headers=headers)
    except httpx.TimeoutException as error:
        raise upstream_timeout("direct fetch") from error
    except httpx.RequestError as error:
        raise ClientFacingError(
            "Could not fetch the direct content. Check that the URL is reachable."
        ) from error
    if response.status_code >= 400:
        raise http_service_error("direct fetch", response.status_code)
    content = response.content
    if len(content) > direct_config.max_bytes:
        raise ClientFacingError(
            f"Direct content is larger than the allowed {direct_config.max_bytes} bytes."
        )
    if target.response_format == "mediawiki_api":
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ClientFacingError("MediaWiki API returned malformed JSON.") from error
        return extract_mediawiki_content(payload)
    return content.decode(response.encoding or "utf-8", errors="replace")


def _github_raw_url(url: str, host: str, config: DirectFetchConfig) -> str | None:
    parsed = urlparse(url)
    if host in {"raw.githubusercontent.com", "gist.githubusercontent.com"}:
        return url if _is_text_path(parsed.path, config) else None
    parts = _path_parts(parsed.path)
    if len(parts) < 5 or parts[2] not in {"blob", "raw"}:
        return None
    file_path = "/".join(parts[4:])
    if not _is_text_path(file_path, config):
        return None
    return f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/{parts[3]}/{file_path}"


def _huggingface_raw_url(url: str, host: str, config: DirectFetchConfig) -> str | None:
    parsed = urlparse(url)
    parts = _path_parts(parsed.path)
    marker_index = _huggingface_marker_index(parts)
    if marker_index is None or len(parts) <= marker_index + 2:
        return None
    file_path = "/".join(parts[marker_index + 2 :])
    if not _is_text_path(file_path, config):
        return None
    repo = "/".join(parts[:marker_index])
    revision = parts[marker_index + 1]
    return f"https://{host}/{repo}/resolve/{revision}/{file_path}"


def _huggingface_marker_index(parts: list[str]) -> int | None:
    minimum = 2 if parts[:1] in (["datasets"], ["spaces"]) else 1
    for index, part in enumerate(parts):
        if index >= minimum and part in {"blob", "raw", "resolve"}:
            return index
    return None


def _gitlab_raw_url(url: str, host: str, config: DirectFetchConfig) -> str | None:
    parsed = urlparse(url)
    parts = _path_parts(parsed.path)
    if "-" not in parts:
        return None
    dash = parts.index("-")
    if len(parts) <= dash + 3 or parts[dash + 1] not in {"blob", "raw"}:
        return None
    file_path = "/".join(parts[dash + 3 :])
    if not _is_text_path(file_path, config):
        return None
    project = "/".join(parts[:dash])
    return f"https://{host}/{project}/-/raw/{parts[dash + 2]}/{file_path}"


def _bitbucket_raw_url(url: str, host: str, config: DirectFetchConfig) -> str | None:
    parsed = urlparse(url)
    parts = _path_parts(parsed.path)
    if len(parts) < 5 or parts[2] not in {"src", "raw"}:
        return None
    file_path = "/".join(parts[4:])
    if not _is_text_path(file_path, config):
        return None
    return f"https://{host}/{parts[0]}/{parts[1]}/raw/{parts[3]}/{file_path}"


def _microsoft_learn_markdown_url(url: str) -> str:
    parsed = urlparse(url)
    query = [
        (name, value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
        if name.lower() != "accept"
    ]
    query.append(("accept", "text/markdown"))
    return parsed._replace(query=urlencode(query)).geturl()


def _is_text_path(path: str, config: DirectFetchConfig) -> bool:
    lower_path = path.lower()
    if any(
        lower_path.endswith(extension.lower())
        for extension in config.text_file_extensions
    ):
        return True
    name = PurePosixPath(path).name.lower()
    return name in {configured.lower() for configured in config.text_file_names}


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]
