"""Notion HTTP 传输。"""

from collections.abc import Callable
from typing import Any

NOTION_VERSION = "2022-06-28"
NOTION_PAGES_URL = "https://api.notion.com/v1/pages"
NOTION_BLOCK_CHILDREN_URL = "https://api.notion.com/v1/blocks/{block_id}/children"


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

    def append_block_children(self, token: str, block_id: str, children: list[dict]) -> None:
        response = self._session_provider().patch(
            NOTION_BLOCK_CHILDREN_URL.format(block_id=block_id),
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            json={"children": children},
            timeout=20,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                response.text[:500] or f"Notion API error: {response.status_code}"
            )
