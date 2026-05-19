from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlencode, unquote, urlparse
import httpx
from web_mcp.config import DirectFetchConfig, HttpConfig
from web_mcp.errors import ClientFacingError, http_service_error, upstream_timeout


@dataclass(frozen=True)
class DirectFetchTarget:
    original_url: str
    raw_url: str


def resolve_direct_fetch_target(
    url: str, config: DirectFetchConfig
) -> DirectFetchTarget | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host in config.github_hosts:
        raw_url = _github_raw_url(url, host, config)
    elif host in config.huggingface_hosts:
        raw_url = _huggingface_raw_url(url, host, config)
    elif host in config.gitlab_hosts:
        raw_url = _gitlab_raw_url(url, host, config)
    elif host in config.bitbucket_hosts:
        raw_url = _bitbucket_raw_url(url, host, config)
    elif _is_wikipedia_host(host):
        raw_url = _wikipedia_raw_url(url, host)
    else:
        raw_url = None
    if raw_url is None:
        return None
    return DirectFetchTarget(original_url=url, raw_url=raw_url)


async def fetch_direct_text(
    target: DirectFetchTarget, direct_config: DirectFetchConfig, http_config: HttpConfig
) -> str:
    headers = {
        "Accept": "text/plain,*/*",
        "Range": f"bytes=0-{direct_config.max_bytes}",
    }
    timeout = httpx.Timeout(http_config.direct_fetch_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(target.raw_url, headers=headers)
    except httpx.TimeoutException as error:
        raise upstream_timeout("direct file fetch") from error
    except httpx.RequestError as error:
        raise ClientFacingError(
            "Could not fetch the direct text file. Check that the URL is reachable."
        ) from error
    if response.status_code >= 400:
        raise http_service_error("direct file fetch", response.status_code)
    content = response.content
    if len(content) > direct_config.max_bytes:
        raise ClientFacingError(
            f"Direct text file is larger than the allowed {direct_config.max_bytes} bytes."
        )
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


def _is_wikipedia_host(host: str) -> bool:
    return host == "wikipedia.org" or host.endswith(".wikipedia.org")


def _wikipedia_raw_url(url: str, host: str) -> str | None:
    parsed = urlparse(url)
    if parsed.path.startswith("/wiki/"):
        title = unquote(parsed.path.removeprefix("/wiki/"))
        if not title:
            return None
        return _wikipedia_index_url(host, {"title": title, "action": "raw"})
    if parsed.path != "/w/index.php":
        return None
    query = parse_qs(parsed.query)
    title = _first_query_value(query, "title")
    if not title:
        return None
    params = {"title": title, "action": "raw"}
    oldid = _first_query_value(query, "oldid")
    if oldid:
        params["oldid"] = oldid
    return _wikipedia_index_url(host, params)


def _wikipedia_index_url(host: str, params: dict[str, str]) -> str:
    return f"https://{host}/w/index.php?{urlencode(params)}"


def _first_query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


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
