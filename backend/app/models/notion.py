from pydantic import BaseModel


class NotionDailyReviewExportRequest(BaseModel):
    date: str


class NotionAnalysisExportRequest(BaseModel):
    code: str


class NotionExportResponse(BaseModel):
    page_id: str
    url: str
    title: str
