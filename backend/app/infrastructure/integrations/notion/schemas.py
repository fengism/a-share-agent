from pydantic import BaseModel


class NotionExportResponse(BaseModel):
    """Purpose: Notion 导出操作的响应结果。"""
    page_id: str
    url: str
    title: str
