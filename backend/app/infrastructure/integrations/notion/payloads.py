"""Notion 页面载荷构造。"""

from app.configuration.schema import Settings
from app.infrastructure.integrations.notion.errors import NotionConfigError


def resolve_parent(settings: Settings) -> dict:
    if not settings.notion_enabled:
        raise NotionConfigError("NOTION_ENABLED must be true to export to Notion")
    if not settings.notion_api_token.strip():
        raise NotionConfigError("NOTION_API_TOKEN is required to export to Notion")
    if settings.notion_database_id.strip():
        return {"database_id": settings.notion_database_id.strip()}
    if settings.notion_parent_page_id.strip():
        return {"page_id": settings.notion_parent_page_id.strip()}
    raise NotionConfigError(
        "NOTION_DATABASE_ID or NOTION_PARENT_PAGE_ID is required to export to Notion"
    )


def page_properties(title: str, parent: dict) -> dict:
    if "database_id" in parent:
        return {"Name": {"title": [{"type": "text", "text": {"content": title}}]}}
    return {"title": {"title": [{"type": "text", "text": {"content": title}}]}}
