from __future__ import annotations
from typing import Any
import httpx
from web_mcp.config import HttpConfig, JinaConfig
from web_mcp.errors import ClientFacingError, http_service_error, upstream_timeout


class JinaReaderClient:
    def __init__(self, jina_config: JinaConfig, http_config: HttpConfig) -> None:
        self._jina_config = jina_config
        self._timeout = httpx.Timeout(http_config.timeout_seconds)

    async def read_markdown(self, url: str, api_key: str) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Return-Format": self._jina_config.return_format,
            "X-Engine": self._jina_config.engine,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=True
            ) as client:
                response = await client.post(
                    self._jina_config.endpoint, headers=headers, json={"url": url}
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
