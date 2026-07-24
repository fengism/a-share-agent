import requests

from app.config import Settings, get_effective_settings
from app.models.notion import NotionExportResponse

_NOTION_VERSION = "2022-06-28"
_NOTION_PAGES_URL = "https://api.notion.com/v1/pages"


class NotionConfigError(RuntimeError):
    """Purpose: Notion 推送相关配置缺失或非法时抛出的异常。"""


def _resolve_parent(settings: Settings) -> dict:
    """根据配置解析 Notion 页面或数据库的 parent 字段。

    Param:
        settings: 应用配置实例
    Return:
        包含 database_id 或 page_id 的 parent dict
    """
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
    """根据 parent 类型构造 Notion 页面 properties。

    Param:
        title: 页面标题
        parent: parent dict，含 database_id 或 page_id
    Return:
        Notion properties dict
    """
    if "database_id" in parent:
        return {"Name": {"title": [{"type": "text", "text": {"content": title}}]}}
    return {"title": {"title": [{"type": "text", "text": {"content": title}}]}}


def create_page(title: str, blocks: list[dict]) -> NotionExportResponse:
    """在 Notion 中创建页面并写入块内容。

    Param:
        title: 页面标题
        blocks: Notion 块 dict 列表
    Return:
        NotionExportResponse，包含 page_id、url 和 title
    """
    settings = get_effective_settings()
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
