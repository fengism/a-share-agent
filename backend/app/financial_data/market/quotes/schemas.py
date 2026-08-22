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
    updated_at: str = ""
    unit: str = "亿元"
    points: list[HsgtFlowPoint] = Field(default_factory=list)


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
    amount: int = 0
    turnover_rate: float | None = None
    float_amount: int = 0
    main_buy: int = 0
    main_sell: int = 0
    main_net: int = 0
    buy_ratio: float | None = None
    sell_ratio: float | None = None
    net_ratio: float | None = None
    limit_tag: str = ""
    rank_tag: str = ""
    recent_chg: float | None = None
    limit_count: int = 0
    chg_1d: float | None = None
    chg_5d: float | None = None
    chg_20d: float | None = None


class MarketSectorStocksHistoryResponse(BaseModel):
    source: Literal["开盘红"] = "开盘红"
    date: str
    plate_id: str
    fetched_at: str
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
