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
    category: str
    source_api: str


class PolicyNewsSnapshotItem(BaseModel):
    title: str
    content: str = ""
    source: str = ""
    publish_time: str = ""
    url: str = ""
    event_type: Literal["policy", "macro", "global", "industry", "market"] = "market"
    direction: Literal["positive", "negative", "mixed", "neutral"] = "neutral"
    timing: Literal["before", "on_date", "after"] = "on_date"
    related_sectors: list[str] = Field(default_factory=list)
    corroborating_sources: list[str] = Field(default_factory=list)


class DailyReviewEventImpact(BaseModel):
    event_title: str
    event_type: Literal["policy", "macro", "global", "industry", "market"] = "market"
    direction: Literal["positive", "negative", "mixed", "neutral"] = "neutral"
    timing: Literal["before", "on_date", "after"] = "on_date"
    horizon: Literal["intraday", "short_term", "medium_term"] = "short_term"
    affected_sectors: list[str] = Field(default_factory=list)
    transmission_chain: str = ""
    evidence: str = ""
    market_confirmation: str = ""
    confirmation_signals: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)


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
    amount_average_20_day: float | None
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
    policy_news: list[PolicyNewsSnapshotItem] = Field(default_factory=list)
    top_sectors: list[SectorSnapshotItem] = Field(default_factory=list)
    bottom_sectors: list[SectorSnapshotItem] = Field(default_factory=list)
    market_volume: MarketVolumeSnapshot = Field(default_factory=dict)
    macro_data: dict[str, Any] = Field(default_factory=dict)
    macro_analysis: dict[str, Any] = Field(default_factory=dict)
    limit_up_ladder: dict[str, Any] = Field(default_factory=dict)
    limit_break_pool: dict[str, Any] = Field(default_factory=dict)
    northbound_funds: dict[str, Any] = Field(default_factory=dict)


# 复盘快照/结果的结构版本：任何会影响已缓存复盘内容的结构变更都要 +1，
# pipeline 会据此自动作废旧缓存（旧记录保留自己的历史值）。
DAILY_REVIEW_SCHEMA_VERSION = 8


class DailyReviewSentimentCycle(BaseModel):
    """短线情绪周期定位（复盘深度的核心判断）。"""

    stage: Literal["冰点", "修复回暖", "主升共振", "高位分化", "退潮杀跌"]
    ladder_health: str = ""
    evidence: list[str] = Field(default_factory=list)


class DailyReviewScenario(BaseModel):
    """次日三情景（超预期 / 符合预期 / 低于预期）应对预案。"""

    name: Literal["超预期", "符合预期", "低于预期"]
    trigger: str = ""
    playbook: str = ""
    watch_levels: list[str] = Field(default_factory=list)


class DailyReviewWatchItem(BaseModel):
    """次日盯盘锚点个股。"""

    name: str
    code: str = ""
    role: Literal["总龙头", "连板最高板", "中军容量票", "负反馈票"] = "总龙头"
    reason: str = ""
    trigger: str = ""


class DailyReviewIndexMove(BaseModel):
    """复盘日主要指数表现（写进周期记录，供次日自检对照）。"""

    code: str = ""
    name: str
    change_pct: float | None = None


class DailyReviewWatchCheck(BaseModel):
    """单只观察标的的次日验证结果。"""

    name: str
    code: str = ""
    role: str = ""
    change_pct: float | None = None
    hit: bool = False  # 次日收涨
    limit_up: bool = False  # 次日涨停（按 9.8% 近似判定）
    missing: bool = False  # 次日无本地行情（停牌/退市/未入库）


class DailyReviewIndexCheck(BaseModel):
    """指数次日验证：复盘日涨跌幅 vs 次日实际涨跌幅。"""

    code: str = ""
    name: str
    previous_change_pct: float | None = None
    change_pct: float | None = None


class DailyReviewPreviousCheck(BaseModel):
    """上一交易日复盘的次日验证结果（复盘闭环的输入）。"""

    review_date: str
    verified_date: str
    indices: list[DailyReviewIndexCheck] = Field(default_factory=list)
    watchlist: list[DailyReviewWatchCheck] = Field(default_factory=list)
    hit_count: int = 0
    checked_count: int = 0
    hit_rate: float | None = None
    previous_stage: str = ""
    limit_up_count: int | None = None
    previous_limit_up_count: int | None = None
    limit_up_delta: int | None = None
    note: str = ""


class DailyReviewCycleRecord(BaseModel):
    """按交易日存放的全局复盘摘要，用于情绪周期趋势与次日自检。

    只保留市场级事实与复盘结论，不含任何用户数据，因此可以跨用户共享。
    """

    date: str
    stage: str = ""
    ladder_health: str = ""
    indices: list[DailyReviewIndexMove] = Field(default_factory=list)
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    up_down_ratio: float | None = None
    break_rate: float | None = None
    watchlist: list[DailyReviewWatchItem] = Field(default_factory=list)
    key_levels: list[str] = Field(default_factory=list)


class CycleTrendPoint(BaseModel):
    """情绪周期趋势上的单个交易日。"""

    date: str
    stage: str = ""
    ladder_health: str = ""
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    break_rate: float | None = None
    up_down_ratio: float | None = None
    index_change_pct: float | None = None
    next_index_change_pct: float | None = None
    stage_transition: str = ""


class CycleStageStat(BaseModel):
    """同一情绪阶段的次日表现统计（阶段胜率）。"""

    stage: str
    occurrences: int = 0
    next_day_up_ratio: float | None = None
    avg_next_day_index_change_pct: float | None = None
    avg_limit_up_delta: float | None = None


class CycleTrend(BaseModel):
    points: list[CycleTrendPoint] = Field(default_factory=list)
    stage_stats: list[CycleStageStat] = Field(default_factory=list)
    note: str = ""


class DailyReviewResult(BaseModel):
    schema_version: int = DAILY_REVIEW_SCHEMA_VERSION
    date: str
    requested_date: str = ""
    effective_date: str = ""
    session_status: Literal["completed", "adjusted"] = "completed"
    quality_status: Literal["complete", "degraded"] = "complete"
    generation_status: Literal["llm", "fallback"] = "fallback"
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
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
    news_policy_review: DailyReviewSection = Field(default_factory=lambda: DailyReviewSection(
        title="新闻政策与影响传导",
        summary="暂无可核验的新闻政策影响分析。",
    ))
    event_impacts: list[DailyReviewEventImpact] = Field(default_factory=list)
    risk_alerts: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    strategy_notes: list[str] = Field(default_factory=list)
    # 深度输出：情绪周期定位 / 三情景预案 / 次日观察锚点 / 关键点位。
    # 兜底稿不编造这些判断，因此 sentiment_cycle 允许为空。
    sentiment_cycle: DailyReviewSentimentCycle | None = None
    scenario_plans: list[DailyReviewScenario] = Field(default_factory=list)
    next_day_watchlist: list[DailyReviewWatchItem] = Field(default_factory=list)
    key_levels: list[str] = Field(default_factory=list)
    # 复盘闭环：用次日真实行情校验上一交易日的观察标的与预判。
    previous_review_check: DailyReviewPreviousCheck | None = None
    # 情绪周期历史趋势：由全局按日摘要推导，供复盘与前端展示历史坐标。
    cycle_trend: CycleTrend | None = None
    data_snapshot: DailyReviewDataSnapshot
