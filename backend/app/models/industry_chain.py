from pydantic import BaseModel, Field


class IndustryChainResult(BaseModel):
    """Purpose: 产业链分析结果，包含上中下游公司、行业驱动力/风险、关键标的、LLM 点评及图表数据。"""
    name: str = ""
    summary: str = ""
    upstream: list[dict] = Field(default_factory=list)
    midstream: list[dict] = Field(default_factory=list)
    downstream: list[dict] = Field(default_factory=list)
    drivers: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    key_stocks: list[dict] = Field(default_factory=list)
    llm_review: str = ""
    charts: list[dict] = Field(default_factory=list)


class IndustryChainProgress(BaseModel):
    """Purpose: 产业链分析进度的 SSE 推送事件载荷。"""
    type: str  # stage_started | stage_completed | complete | error
    stage: str = ""
    message: str = ""
    result: dict | None = None


class IndustryChainHistoryItem(BaseModel):
    """Purpose: 产业链分析历史列表的单条摘要。"""
    name: str
    archive_id: str
    saved_at: str = ""
    title: str = ""
    summary: str = ""
