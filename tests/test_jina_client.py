from __future__ import annotations
import httpx
from jina_client import _extract_content


def test_extract_content_from_jina_data_payload() -> None:
    response = httpx.Response(200, json={"data": {"content": "# Title\nBody"}})
    assert _extract_content(response) == "# Title\nBody"
