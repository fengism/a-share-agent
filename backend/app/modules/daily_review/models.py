from typing import Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.domain.prompting import PromptTrace


class IndexSnapshotItem(TypedDict, total=False):
    code: str
    name: str
    price: float | None
    change_pct: float | None
    volume: float | None
    amount: float | None
    open: float | None
    high: float | None
    low: float | None
    amplitude: float | None
    pre_close: float | None


class HotRankSnapshotItem(TypedDict, total=False):
    rank: int | None
    code: str
    name: str
    change_pct: float | None
    hot_value: float | None
    concept_tag: str
    pop_tag: str
    hot_tag: str
    tag: Any


class DragonTigerSnapshotItem(TypedDict, total=False):
    code: str
    name: str
    trade_date: str
    close: float | None
    change_pct: float | None
    turnover_pct: float | None
    net_amount: float | None
    buy_amount: float | None
    sell_amount: float | None
    deal_amount: float | None
    total_amount: float | None
    net_amount_rate: float | None
    deal_amount_rate: float | None
    reason: str
    explain: str
    d1_chg: float | None
    d2_chg: float | None
    d5_chg: float | None


class SectorSnapshotItem(TypedDict, total=False):
    name: str
    change_pct: float | None
    change_pct_5d: float | None
    change_pct_20d: float | None
    leading_stock: str
    leading_change_pct: float | None


class MarketNewsSnapshotItem(TypedDict, total=False):
    title: str
    content: str
    source: str
    publish_time: str
    url: str
    author: str
    read_count: int
    comment_count: int
    image_url: str


class MarketBreadthSnapshot(TypedDict, total=False):
    date: str | None
    source: str | None
    up_count: int
    down_count: int
    flat_count: int
    limit_up_count: int
    limit_down_count: int
    total_stocks: int
    limit_up_stocks: list[dict[str, Any]]
    limit_down_stocks: list[dict[str, Any]]
    stock_pct_distribution: list[dict[str, Any]]
    partial: bool
    unavailable_sections: list[str]
    field_sources: dict[str, str]
    source_apis: dict[str, str]


class MarketVolumeSnapshot(TypedDict, total=False):
    date: str | None
    amount: float | None
    amount_before_one_day: float | None
    amount_average_60_day: float | None


class DailyReviewSection(BaseModel):
    title: str
    summary: str
    bullets: list[str] = Field(default_factory=list)


class DailyReviewSourceStatus(BaseModel):
    status: Literal["complete", "partial", "unavailable"] = "unavailable"
    requested_date: str = ""
    data_date: str = ""
    provider: str = ""
    is_realtime: bool = False
    error: str = ""


class DailyReviewDataSnapshot(BaseModel):
    requested_date: str = ""
    effective_date: str = ""
    source_status: dict[str, DailyReviewSourceStatus] = Field(default_factory=dict)
    indices: list[IndexSnapshotItem] = Field(default_factory=list)
    hot_stocks: list[HotRankSnapshotItem] = Field(default_factory=list)
    hot_concepts: list[HotRankSnapshotItem] = Field(default_factory=list)
    hot_industries: list[HotRankSnapshotItem] = Field(default_factory=list)
    dragon_tiger: list[DragonTigerSnapshotItem] = Field(default_factory=list)
    market_statistics: MarketBreadthSnapshot = Field(default_factory=dict)
    market_news: list[MarketNewsSnapshotItem] = Field(default_factory=list)
    top_sectors: list[SectorSnapshotItem] = Field(default_factory=list)
    bottom_sectors: list[SectorSnapshotItem] = Field(default_factory=list)
    market_volume: MarketVolumeSnapshot = Field(default_factory=dict)
    macro_data: dict[str, Any] = Field(default_factory=dict)


class DailyReviewResult(BaseModel):
    schema_version: int = 3
    date: str
    requested_date: str = ""
    effective_date: str = ""
    session_status: Literal["completed", "adjusted"] = "completed"
    quality_status: Literal["complete", "degraded"] = "complete"
    generation_status: Literal["llm", "fallback"] = "fallback"
    warnings: list[str] = Field(default_factory=list)
    source_errors: dict[str, str] = Field(default_factory=dict)
    llm_error: str = ""
    market_state: Literal["attack", "balanced", "defensive", "unknown"] = "unknown"
    position_range: str = ""
    invalid_conditions: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    prompt_trace: PromptTrace | None = None
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
