import requests

from app.config import Settings, get_settings
from app.models.notion import NotionExportResponse

_NOTION_VERSION = "2022-06-28"
_NOTION_PAGES_URL = "https://api.notion.com/v1/pages"


class NotionConfigError(RuntimeError):
    pass


def _resolve_parent(settings: Settings) -> dict:
    if not settings.notion_enabled:
        raise NotionConfigError("NOTION_ENABLED must be true to export to Notion")
    if not settings.notion_api_token.strip():
        raise NotionConfigError("NOTION_API_TOKEN is required to export to Notion")
    if settings.notion_database_id.strip():
        return {"database_id": settings.notion_database_id.strip()}
    if settings.notion_parent_page_id.strip():
        return {"page_id": settings.notion_parent_page_id.strip()}
    raise NotionConfigError("NOTION_DATABASE_ID or NOTION_PARENT_PAGE_ID is required to export to Notion")


def _properties(title: str, parent: dict) -> dict:
    if "database_id" in parent:
        return {"Name": {"title": [{"type": "text", "text": {"content": title}}]}}
    return {"title": {"title": [{"type": "text", "text": {"content": title}}]}}


def create_page(title: str, blocks: list[dict]) -> NotionExportResponse:
    settings = get_settings()
    parent = _resolve_parent(settings)
    response = requests.post(
        _NOTION_PAGES_URL,
        headers={
            "Authorization": f"Bearer {settings.notion_api_token.strip()}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json={
            "parent": parent,
            "properties": _properties(title, parent),
            "children": blocks,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text[:500] or f"Notion API error: {response.status_code}")
    data = response.json()
    return NotionExportResponse(page_id=str(data.get("id", "")), url=str(data.get("url", "")), title=title)
