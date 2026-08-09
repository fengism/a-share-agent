"""Notion HTTP 传输。"""

from collections.abc import Callable
from typing import Any

NOTION_VERSION = "2022-06-28"
NOTION_PAGES_URL = "https://api.notion.com/v1/pages"


class NotionTransport:
    def __init__(self, session_provider: Callable[[], Any]) -> None:
        self._session_provider = session_provider

    def create_page(self, token: str, payload: dict) -> dict:
        response = self._session_provider().post(
            NOTION_PAGES_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                response.text[:500] or f"Notion API error: {response.status_code}"
            )
        return response.json()
