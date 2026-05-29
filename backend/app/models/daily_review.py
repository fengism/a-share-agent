from pydantic import BaseModel, Field


class DailyReviewRequest(BaseModel):
    date: str | None = None
    force: bool = False


class DailyReviewSection(BaseModel):
    title: str
    summary: str
    bullets: list[str] = Field(default_factory=list)


class DailyReviewDataSnapshot(BaseModel):
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
    date: str
    title: str
    generated_at: str
    market_summary: str
