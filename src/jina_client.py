from __future__ import annotations
import json
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
    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    if content_type == "text/event-stream":
        return _extract_event_stream_content(response.text)
    try:
        payload: Any = response.json()
    except ValueError:
        return response.text
    content = _extract_payload_content(payload)
    if content is not None:
        return content
    raise ClientFacingError(
        "Jina returned an unsupported response. Retry later or try another URL."
    )


def _extract_payload_content(payload: Any) -> str | None:
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, dict):
            for key in ("content", "markdown", "text"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
        if isinstance(data, str):
            return data
        for key in ("content", "markdown", "text"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
    if isinstance(payload, str):
        return payload
    return None


def _extract_event_stream_content(text: str) -> str:
    chunks: list[str] = []
    event_lines: list[str] = []
    for line in text.splitlines():
        if line == "":
            _append_event_stream_chunk(chunks, event_lines)
            event_lines = []
            continue
        if line.startswith("data:"):
            data = line[5:]
            event_lines.append(data[1:] if data.startswith(" ") else data)
    _append_event_stream_chunk(chunks, event_lines)
    if chunks:
        return "".join(chunks)
    return text


def _append_event_stream_chunk(chunks: list[str], event_lines: list[str]) -> None:
    if not event_lines:
        return
    data = "\n".join(event_lines)
    if data == "[DONE]":
        return
    try:
        payload: Any = json.loads(data)
    except ValueError:
        chunks.append(data)
        return
    content = _extract_payload_content(payload)
    if content is not None:
        chunks.append(content)


def _header_bool(value: bool) -> str:
    return "true" if value else "false"
