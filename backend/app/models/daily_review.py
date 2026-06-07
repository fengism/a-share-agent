from pydantic import BaseModel, Field


class DailyReviewRequest(BaseModel):
    """Purpose: 每日复盘接口的请求参数。"""
    date: str | None = None
    force: bool = False


class DailyReviewSection(BaseModel):
    """Purpose: 每日复盘中单个章节的内容（标题/摘要/要点）。"""
    title: str
    summary: str
    bullets: list[str] = Field(default_factory=list)


class DailyReviewDataSnapshot(BaseModel):
    """Purpose: 每日复盘所引用的市场数据快照，用于回溯复盘生成时的市场状态。"""
    indices: list[dict] = Field(default_factory=list)
    hot_stocks: list[dict] = Field(default_factory=list)
    hot_concepts: list[dict] = Field(default_factory=list)
    hot_industries: list[dict] = Field(default_factory=list)
    dragon_tiger: list[dict] = Field(default_factory=list)
    market_statistics: dict = Field(default_factory=dict)
    market_news: list[dict] = Field(default_factory=list)
    top_sectors: list[dict] = Field(default_factory=list)
    bottom_sectors: list[dict] = Field(default_factory=list)
    market_volume: dict = Field(default_factory=dict)


class DailyReviewResult(BaseModel):
    """Purpose: 每日复盘的完整结果，包括各章节、LLM 点评、风险/机会/策略要点及数据快照。"""
    date: str
    title: str
    generated_at: str
    market_summary: str
    llm_review: str = ""
    index_review: DailyReviewSection
    hotspot_review: DailyReviewSection
    dragon_tiger_review: DailyReviewSection
    risk_alerts: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    strategy_notes: list[str] = Field(default_factory=list)
    data_snapshot: DailyReviewDataSnapshot
    market_volume: dict = Field(default_factory=dict)


class DailyReviewHistoryItem(BaseModel):
    """Purpose: 每日复盘历史列表的单条摘要。"""
    date: str
    title: str
    generated_at: str
    market_summary: str
