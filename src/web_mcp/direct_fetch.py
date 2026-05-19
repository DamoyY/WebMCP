from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse
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
    elif host in config.gitlab_hosts:
        raw_url = _gitlab_raw_url(url, host, config)
    elif host in config.bitbucket_hosts:
        raw_url = _bitbucket_raw_url(url, host, config)
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
