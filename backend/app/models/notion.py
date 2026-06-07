from pydantic import BaseModel


class NotionDailyReviewExportRequest(BaseModel):
    """Purpose: 每日复盘导出到 Notion 的请求参数。"""
    date: str


class NotionAnalysisExportRequest(BaseModel):
    """Purpose: 个股分析导出到 Notion 的请求参数。"""
    code: str


class NotionExportResponse(BaseModel):
    """Purpose: Notion 导出操作的响应结果。"""
    page_id: str
    url: str
    title: str
