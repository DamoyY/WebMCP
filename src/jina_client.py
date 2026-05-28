from __future__ import annotations
from typing import Any
import httpx
from config import HttpConfig, JinaConfig
from errors import ClientFacingError, http_service_error, upstream_timeout


class JinaReaderClient:
    def __init__(self, jina_config: JinaConfig, http_config: HttpConfig) -> None:
        self._jina_config = jina_config
        self._timeout = httpx.Timeout(http_config.timeout_seconds)

    async def read_markdown(self, url: str, api_key: str) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": self._jina_config.accept,
            "Content-Type": "application/json",
            "X-Engine": self._jina_config.engine,
            "X-Locale": self._jina_config.locale,
            "X-No-Cache": _header_bool(self._jina_config.no_cache),
            "X-Respond-With": self._jina_config.respond_with,
            "X-Retain-Images": self._jina_config.retain_images,
            "X-Return-Format": self._jina_config.return_format,
            "X-With-Shadow-Dom": _header_bool(self._jina_config.with_shadow_dom),
        }
        payload = {"url": url, "viewport": self._jina_config.viewport.model_dump()}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=True
            ) as client:
                response = await client.post(
                    self._jina_config.endpoint, headers=headers, json=payload
                )
        except httpx.TimeoutException as error:
            raise upstream_timeout("Jina") from error
        except httpx.RequestError as error:
            raise ClientFacingError(
                "Could not reach Jina. Check network connectivity and retry."
            ) from error
        if response.status_code >= 400:
            raise http_service_error("Jina", response.status_code)
        return _extract_content(response)


def _extract_content(response: httpx.Response) -> str:
    try:
        payload: Any = response.json()
    except ValueError:
        return response.text
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, dict):
            for key in ("content", "markdown", "text"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
        for key in ("content", "markdown", "text"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
    if isinstance(payload, str):
        return payload
    raise ClientFacingError(
        "Jina returned an unsupported response. Retry later or try another URL."
    )


def _header_bool(value: bool) -> str:
    return "true" if value else "false"
