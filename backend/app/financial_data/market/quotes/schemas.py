from typing import Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarketVolumeSeriesItem(BaseModel):
    date: str
    volume: float = 0.0
    amount: float = 0.0


class MarketVolumeResponse(BaseModel):
    items: list[MarketVolumeSeriesItem] = Field(default_factory=list)
    partial: bool = False
    unavailable_markets: list[Literal["shanghai", "shenzhen"]] = Field(default_factory=list)
    market_sources: dict[str, str] = Field(default_factory=dict)
    source_apis: dict[str, str] = Field(default_factory=dict)


class ThsHotStock(BaseModel):
    model_config = ConfigDict(extra="allow")

    rank: int | None = None
    code: str = ""
    name: str = ""
    change_pct: float | None = None
    hot_value: float | None = None
    concept_tag: str = ""
    pop_tag: str = ""


class ThsHotPlate(BaseModel):
    model_config = ConfigDict(extra="allow")

    rank: int | None = None
    code: str = ""
    name: str = ""
    change_pct: float | None = None
    hot_value: float | None = None
    hot_tag: str = ""
    tag: str = ""


class DragonTigerItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str = ""
    name: str = ""
    trade_date: str = ""
    close: float | None = None
    change_pct: float | None = None
    turnover_pct: float | None = None
    net_amount: float | None = None
    buy_amount: float | None = None
    sell_amount: float | None = None
    deal_amount: float | None = None
    total_amount: float | None = None
    net_amount_rate: float | None = None
    deal_amount_rate: float | None = None
    reason: str = ""
    explain: str = ""
    d1_chg: float | None = None
    d2_chg: float | None = None
    d5_chg: float | None = None

    @field_validator("reason", "explain", mode="before")
    @classmethod
    def normalize_nullable_descriptions(cls, value):
        return value or ""


class DragonTigerDetail(BaseModel):
    side: Literal["buy", "sell"]
    code: str
    operate_name: str
    buy_amount: float | None
    sell_amount: float | None
    net_amount: float | None
    buy_ratio: float | None
    sell_ratio: float | None


class IndustryRankItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    rank: int | None = None
    name: str = ""
    change_pct: float | None = None
    code: str = ""
    up_count: int | None = None
    down_count: int | None = None
    leader: str = ""
    leader_change: float | None = None
    amount: int | None = None
    net_inflow: int | None = None
    buy_amount: int | None = None
    sell_amount: int | None = None
    turnover_rate: float | None = None
    market_cap: int | None = None
    avg_change: float | None = None


class IndustryRankings(BaseModel):
    sectors: list[IndustryRankItem] = Field(default_factory=list)
    total: int = 0
    source: str = ""
    date: str = ""
    fetched_at: str = ""
    fund_data_available: bool = False


class HsgtFlowPoint(BaseModel):
    time: str
    hgt: float | None = None
    sgt: float | None = None
    total: float | None = None


class HsgtFlowResponse(BaseModel):
    date: str = ""
    updated_at: str = ""
    unit: str = "亿元"
    is_stale: bool = False
    points: list[HsgtFlowPoint] = Field(default_factory=list)


class NorthboundHistoryPoint(BaseModel):
    date: str
    north_money: float | None = None
    sh_connect: float | None = None
    sz_connect: float | None = None
    south_money: float | None = None
    hs300_open: float | None = None
    hs300_close: float | None = None
    hs300_high: float | None = None
    hs300_low: float | None = None
    hs300_change: float | None = None
    hs300_change_pct: float | None = None


class NorthboundHistoryResponse(BaseModel):
    source: Literal["乐咕乐股", "东方财富"] = "乐咕乐股"
    updated_at: str
    unit: str = "亿元"
    index_name: str = "沪深300"
    is_stale: bool = False
    items: list[NorthboundHistoryPoint] = Field(default_factory=list)


class HsgtFlowHistoryItem(BaseModel):
    date: str
    updated_at: str = ""
    points: list[HsgtFlowPoint] = Field(default_factory=list)


class MarketEmotionDistribution(BaseModel):
    status: bool = False
    suspend_num: int = 0
    up_num: int = 0
    down_num: int = 0
    rise_num: int = 0
    fall_num: int = 0
    flat_num: int = 0
    down_10: int = 0
    down_8: int = 0
    down_6: int = 0
    down_4: int = 0
    down_2: int = 0
    up_2: int = 0
    up_4: int = 0
    up_6: int = 0
    up_8: int = 0
    up_10: int = 0


class MarketLimitUpBoardItem(BaseModel):
    name: str
    count: int = 0
    promotion_rate: str | None = None


class MarketEmotion(BaseModel):
    source: Literal["财联社"] = "财联社"
    fetched_at: str
    market_degree: int | None = None
    shsz_balance: str = ""
    shsz_balance_change_px: str = ""
    preview_balance: str = ""
    preview_balance_change_px: str = ""
    up_ratio: str = ""
    up_ratio_num: int | None = None
    up_open_num: int | None = None
    performance: str = ""
    up_open_ratio: str = ""
    profit_ratio: str = ""
    up_down_dis: MarketEmotionDistribution = Field(default_factory=MarketEmotionDistribution)
    limit_up_board: list[MarketLimitUpBoardItem] = Field(default_factory=list)


class MarketWindPlate(BaseModel):
    plate_code: str
    plate_name: str
    catalyst: str = ""


class MarketWindResponse(BaseModel):
    source: Literal["财联社"] = "财联社"
    fetched_at: str
    items: list[MarketWindPlate] = Field(default_factory=list)


class MarketWindStock(BaseModel):
    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    limit_up_days: int = 0


class MarketWindStocksResponse(BaseModel):
    source: Literal["财联社"] = "财联社"
    fetched_at: str
    plate_code: str
    items: list[MarketWindStock] = Field(default_factory=list)


class TradingCalendarResponse(BaseModel):
    """A 股交易日历区间视图。"""
    start_date: str
    end_date: str
    trade_dates: list[str] = Field(default_factory=list)
    count: int = 0
    today: str
    today_is_trading_day: bool = False
    previous_trading_day: str | None = None
    next_trading_day: str | None = None
    degraded: bool = False


class MarketMarginItem(BaseModel):
    date: str
    rzye: float | None = None
    rqye: float | None = None
    rzrqye: float | None = None
    rzmre: float | None = None
    rzche: float | None = None
    rzjme: float | None = None


class MarketMarginResponse(BaseModel):
    source: Literal["东方财富"] = "东方财富"
    fetched_at: str
    items: list[MarketMarginItem] = Field(default_factory=list)


class MarketPriceAnomalyItem(BaseModel):
    code: str
    name: str
    market: Literal["SH", "SZ", "BJ"]
    change_pct: float | None = None
    deviation: float | None = None
    days: int | None = None
    board: int | None = None
    rule_code: int | None = None
    rule: str
    is_today: bool = False


class MarketPriceAnomalyResponse(BaseModel):
    source: Literal["东方财富"] = "东方财富"
    date: str
    fetched_at: str
    page_no: int
    page_size: int
    pages: int = 0
    is_stale: bool = False
    items: list[MarketPriceAnomalyItem] = Field(default_factory=list)


class MarketPriceAnomalyCountItem(BaseModel):
    code: str
    name: str
    market: Literal["SH", "SZ", "BJ"]
    price: float | None = None
    change_pct: float | None = None
    times: int | None = None
    deviation: float | None = None
    days: int | None = None
    board: int | None = None


class MarketPriceAnomalyCountResponse(BaseModel):
    source: Literal["东方财富"] = "东方财富"
    date: str
    fetched_at: str
    page_no: int
    page_size: int
    pages: int = 0
    is_stale: bool = False
    items: list[MarketPriceAnomalyCountItem] = Field(default_factory=list)


class MarketMainlineFaucetStock(BaseModel):
    code: str
    name: str
    change_pct: float | None = None
    reason: str = ""


class MarketMainlinePlate(BaseModel):
    code: str = ""
    name: str
    reason: str = ""
    rise_count: int | None = None
    change_pct: float | None = None
    article_title: str = ""
    faucets: list[MarketMainlineFaucetStock] = Field(default_factory=list)


class MarketMainlineChance(BaseModel):
    title: str
    description: str = ""
    continued_days: int | None = None
    hot: int | None = None
    plates: list[MarketMainlinePlate] = Field(default_factory=list)


class MarketMainlineStyleIndexStock(BaseModel):
    code: str
    name: str
    change_30d: float | None = None


class MarketMainlineStyleIndex(BaseModel):
    code: str = ""
    name: str = ""
    change_30d: float | None = None
    stocks: list[MarketMainlineStyleIndexStock] = Field(default_factory=list)


class MarketMainlineStyle(BaseModel):
    title: str = ""
    interpret: str = ""
    indexes: list[MarketMainlineStyleIndex] = Field(default_factory=list)


class MarketMainlineResponse(BaseModel):
    source: Literal["财联社"] = "财联社"
    fetched_at: str
    style: MarketMainlineStyle | None = None
    items: list[MarketMainlineChance] = Field(default_factory=list)


class MarketLimitUpLadderStock(BaseModel):
    code: str
    name: str
    board_count: int = 0
    limit_up_time: str = ""
    sector_code: str = ""
    sector_name: str = ""
    one_word: bool = False
    popular: bool = False
    sector_limit_up_count: int = 0
    amount: int = 0
    sector_amount: int = 0


class MarketLimitUpLadderSector(BaseModel):
    sector_code: str = ""
    sector_name: str
    stock_count: int = 0
    amount: int = 0
    stock_codes: list[str] = Field(default_factory=list)


class MarketLimitUpLadderResponse(BaseModel):
    source: Literal["开盘红"] = "开盘红"
    date: str
    fetched_at: str
    total: int = 0
    stocks: list[MarketLimitUpLadderStock] = Field(default_factory=list)
    sectors: list[MarketLimitUpLadderSector] = Field(default_factory=list)


MarketLimitHistoryCategory = Literal["limit_up", "limit_down", "wind_vane"]


class MarketLimitHistoryItem(BaseModel):
    code: str
    name: str
    limit_time: str = ""
    open_time: str = ""
    seal_amount: int = 0
    limit_tag: str = ""
    limit_count: int = 0
    themes: str = ""
    net_inflow: int = 0
    turnover: int = 0
    turnover_rate: float | None = None
    market_cap: int = 0
    reason: str = ""
    seal_money: int = 0
    industry_id: str = ""
    industry_limit_up_count: int = 0


class MarketLimitHistoryResponse(BaseModel):
    source: Literal["开盘红"] = "开盘红"
    date: str
    category: MarketLimitHistoryCategory
    fetched_at: str
    total: int = 0
    items: list[MarketLimitHistoryItem] = Field(default_factory=list)


class MarketSectorStocksHistoryItem(BaseModel):
    code: str
    name: str
    tags: str = ""
    price: float | None = None
    change_pct: float | None = None
    amount: int | None = None
    turnover_rate: float | None = None
    float_amount: int | None = None
    main_buy: int | None = None
    main_sell: int | None = None
    main_net: int | None = None
    buy_ratio: float | None = None
    sell_ratio: float | None = None
    net_ratio: float | None = None
    limit_tag: str = ""
    rank_tag: str = ""
    recent_chg: float | None = None
    limit_count: int | None = None
    chg_1d: float | None = None
    chg_5d: float | None = None
    chg_20d: float | None = None
    quote_source: str | None = None
    quoted_at: str | None = None


class MarketSectorStocksHistoryResponse(BaseModel):
    source: Literal["开盘红"] = "开盘红"
    date: str
    constituent_date: str
    plate_id: str
    fetched_at: str
    quoted_at: str | None = None
    quote_source: str | None = None
    is_realtime: bool = False
    realtime_partial: bool = False
    history_details_available: bool = True
    total: int = 0
    items: list[MarketSectorStocksHistoryItem] = Field(default_factory=list)


class MarketStatistics(BaseModel):
    """Purpose: 市场统计数据，包括板块涨跌榜、涨跌家数、涨停跌停列表和股票涨幅分布。"""
    date: str | None = None
    source: str | None = None
    partial: bool = False
    unavailable_sections: list[
        Literal["sector_rankings", "pct_distribution", "limit_up_pool", "limit_down_pool"]
    ] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)
    source_apis: dict[str, str] = Field(default_factory=dict)

    # 板块涨幅榜
    top_sectors: List[Dict] = Field(default_factory=list)     # 涨幅前5板块
    bottom_sectors: List[Dict] = Field(default_factory=list)  # 跌幅前5板块

    # 涨跌股票榜
    up_count: int = 0                   # 上涨家数
    down_count: int = 0                 # 下跌家数
    flat_count: int = 0                 # 平盘家数
    limit_up_count: int = 0             # 涨停家数
    limit_down_count: int = 0           # 跌停家数
    total_stocks: int = 0               # 总股票数
    limit_up_stocks: List[Dict] = Field(default_factory=list)  # 涨停股票列表
    limit_down_stocks: List[Dict] = Field(default_factory=list)  # 跌停股票列表

    # 股票涨幅分布
    stock_pct_distribution: List[Dict] = Field(default_factory=list)  # 股票涨幅分布


class IndexIntradayItem(BaseModel):
    """单条指数分时行情数据点。"""

    time: str
    price: float
    avg_price: float | None = None
    volume: float | None = None
    amount: float | None = None
    change_pct: float | None = None


class IndexIntradayData(BaseModel):
    """当前交易日指数分时行情。"""

    code: str
    source: str = ""
    prev_close: float | None = None
    items: list[IndexIntradayItem] = Field(default_factory=list)


class MarketBreadthDailySummary(BaseModel):
    date: str
    strong_industry_count: int = 0
    total_industry_count: int = 0
    strong_ratio: float = 0.0


class MarketBreadthResponse(BaseModel):
    source: Literal["本地计算"] = "本地计算"
    fetched_at: str
    completed_market_date: str = ""
    stale: bool = False
    successful_stocks: int = 0
    total_stocks: int = 0
    industries: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    values: list[list[float | None]] = Field(default_factory=list)
    summaries: list[MarketBreadthDailySummary] = Field(default_factory=list)


class NationalTeamEtfPoint(BaseModel):
    date: str
    source: str = "unknown"
    fetched_at: str | None = None
    verification_status: str = "unknown"
    shares_100m: float
    shares_change_100m: float | None = None
    shares_change_pct: float | None = None
    close: float | None = None
    estimated_net_flow_100m: float | None = None


class NationalTeamEtfSeries(BaseModel):
    code: str
    name: str
    fund_manager: str
    exchange: Literal["SH", "SZ"]
    index_key: str
    index_name: str
    latest_date: str | None = None
    latest_shares_100m: float | None = None
    latest_change_1d_100m: float | None = None
    change_5d_100m: float | None = None
    change_20d_100m: float | None = None
    points: list[NationalTeamEtfPoint] = Field(default_factory=list)


class NationalTeamIndexPoint(BaseModel):
    date: str
    total_shares_100m: float
    shares_change_100m: float | None = None
    cumulative_change_100m: float = 0
    index_close: float | None = None
    estimated_net_flow_100m: float | None = None


class NationalTeamIndexSeries(BaseModel):
    index_key: str
    index_name: str
    index_code: str
    etf_codes: list[str] = Field(default_factory=list)
    covered_etf_codes: list[str] = Field(default_factory=list)
    latest_date: str | None = None
    latest_total_shares_100m: float | None = None
    latest_change_1d_100m: float | None = None
    change_5d_100m: float | None = None
    change_20d_100m: float | None = None
    estimated_net_flow_1d_100m: float | None = None
    points: list[NationalTeamIndexPoint] = Field(default_factory=list)


class NationalTeamSummary(BaseModel):
    total_shares_100m: float | None = None
    change_1d_100m: float | None = None
    change_5d_100m: float | None = None
    change_20d_100m: float | None = None
    estimated_net_flow_1d_100m: float | None = None
    estimated_net_flow_5d_100m: float | None = None
    estimated_net_flow_20d_100m: float | None = None


class NationalTeamShareObservation(BaseModel):
    code: str
    source: str
    shares_100m: float
    business_date: str | None = None
    fetched_at: str
    verification_status: Literal["provisional"] = "provisional"


class NationalTeamResponse(BaseModel):
    source: str = "上交所/深交所/东方财富"
    fetched_at: str
    as_of_date: str | None = None
    requested_days: int
    partial: bool = False
    missing_etfs: list[str] = Field(default_factory=list)
    expected_date: str | None = None
    stale: bool = False
    calendar_degraded: bool = False
    refreshing: bool = False
    observations: list[NationalTeamShareObservation] = Field(default_factory=list)
    missing_share_etfs: list[str] = Field(default_factory=list)
    missing_price_etfs: list[str] = Field(default_factory=list)
    missing_indices: list[str] = Field(default_factory=list)
    covered_etf_count: int = 0
    total_etf_count: int = 12
    methodology: str
    disclaimer: str
    summary: NationalTeamSummary = Field(default_factory=NationalTeamSummary)
    indices: list[NationalTeamIndexSeries] = Field(default_factory=list)
    etfs: list[NationalTeamEtfSeries] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 概念板块联动 schemas
# ---------------------------------------------------------------------------


class ConceptSummaryItem(BaseModel):
    """概念列表中的单条摘要（名称 + 成分股只数）。"""

    name: str
    stock_count: int


class ConceptListResponse(BaseModel):
    """``GET /market/concepts`` 响应体。"""

    items: List[ConceptSummaryItem]
    total: int


class ConceptConstituentItem(BaseModel):
    """成分股列表中的单只股票，含实时行情（行情不可用时各字段为 null）。"""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    amount: int | None = None
    quote_source: str | None = None


class RelatedConceptItem(BaseModel):
    """与当前概念重叠最多的相关概念。"""

    name: str
    overlap: int
    ratio: float


class ConceptConstituentResponse(BaseModel):
    """``GET /market/concept/{concept}/constituents`` 响应体。"""

    concept: str
    total: int
    items: List[ConceptConstituentItem]
    related_concepts: List[RelatedConceptItem] = Field(default_factory=list)
    quoted_at: str | None = None
    quote_source: str | None = None
    quote_covered: int = 0


class ConceptIndexPoint(BaseModel):
    """概念等权指数的单根 K 线。"""

    date: str
    open: float
    high: float
    low: float
    close: float
    change_pct: float
    amount: float | None = None
    up_count: int = 0
    down_count: int = 0
    limit_up_count: int = 0
    limit_down_count: int = 0
    sample_count: int = 0


class ConceptIndexResponse(BaseModel):
    """``GET /market/concept/{concept}/index`` 响应体。"""

    concept: str
    method: str
    base: float | None = None
    constituent_total: int
    constituent_used: int
    truncated: bool = False
    items: List[ConceptIndexPoint]
