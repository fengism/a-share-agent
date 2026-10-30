from pydantic import BaseModel, Field, field_validator

from app.domain.stock import StockConcept

SCREENER_MARKETS = frozenset({"主板", "科创板", "创业板", "北交所"})


class ScreenerFilter(BaseModel):
    """Purpose: 股票筛选接口的过滤条件参数。"""

    pe_min: float | None = None
    pe_max: float | None = None
    pb_min: float | None = None
    pb_max: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    market_cap_min: float | None = None  # 亿元
    market_cap_max: float | None = None
    change_pct_min: float | None = None
    change_pct_max: float | None = None
    turnover_pct_min: float | None = None
    turnover_pct_max: float | None = None
    # 题材/量价异动指标：日内振幅 (%)
    amplitude_min: float | None = None
    amplitude_max: float | None = None
    # 题材/动量指标：量比
    volume_ratio_min: float | None = None
    volume_ratio_max: float | None = None
    # 动量指标：近60日涨跌幅 (%)
    change_pct_60d_min: float | None = None
    change_pct_60d_max: float | None = None
    # 深度价值指标：是否仅筛选破净股 (0 < 市净率 PB <= 1.0)
    is_broken_net: bool = False
    industries: list[str] | None = None
    concepts: list[str] | None = None
    # 市场板块筛选：主板/科创板/创业板/北交所，None 表示全部市场
    markets: list[str] | None = Field(default=None, max_length=4)

    @field_validator("markets")
    @classmethod
    def _validate_markets(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        invalid = [item for item in normalized if item not in SCREENER_MARKETS]
        if invalid:
            raise ValueError(f"不支持的市场: {invalid}，可选值: {sorted(SCREENER_MARKETS)}")
        return normalized or None

    # 风控过滤（可选，默认全部关闭，调用方按需开启）：剔除 ST/*ST/退市风险股
    exclude_st: bool = False
    # 上市不满 N 天的新股波动与数据完整性风险高，None 表示不过滤
    min_listing_days: int | None = Field(default=None, ge=0)
    # 当日成交额下限（亿元），过滤流动性不足的标的，None 表示不过滤
    min_amount_yi: float | None = Field(default=None, ge=0)
    sort_by: str = "market_cap"
    sort_order: str = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=1000)


class ScreenerItem(BaseModel):
    """Purpose: 股票筛选结果中的单只股票信息。"""

    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    market_cap: float | None = None  # 亿元
    turnover_pct: float | None = None
    volume: float | None = None
    amplitude: float | None = None
    volume_ratio: float | None = None
    change_pct_60d: float | None = None
    composite_score: float | None = None
    is_broken_net: bool = False
    exchange: str | None = None
    board: str | None = None
    listing_date: str | None = None
    exchange_industry: str | None = None
    first_industry: StockConcept | None = None
    second_industry: StockConcept | None = None
    third_industry: StockConcept | None = None
    concepts: list[str] = Field(default_factory=list)


class ScreenerPreset(BaseModel):
    """Purpose: 题材挖掘与低估值等经典场景预设模版。"""

    key: str
    name: str
    category: str  # "value" | "theme" | "growth"
    description: str
    filters: ScreenerFilter


class ScreenerResult(BaseModel):
    """Purpose: 股票筛选的分页结果。"""

    items: list[ScreenerItem]
    total: int
    page: int
    page_size: int
    sw_industry_coverage: float = Field(default=0, ge=0, le=1)
    exchange_industry_coverage: float = Field(default=0, ge=0, le=1)
    stock_master_complete: bool = False
    # 风控过滤剔除的数量，便于调用方了解口径
    risk_excluded_st: int = 0
    risk_excluded_new_listing: int = 0
    risk_excluded_low_liquidity: int = 0


class ValuationPercentileRequest(BaseModel):
    """Purpose: 估值百分位查询接口的请求参数。"""

    codes: list[str]
    period: str = "近三年"
    indicator: str = "市盈率(TTM)"


class ValuationPercentileItem(BaseModel):
    """Purpose: 单只股票的估值百分位结果。"""

    code: str
    percentile: float | None = None


class ValuationPercentileResult(BaseModel):
    """Purpose: 估值百分位批量查询的返回结果。"""

    items: list[ValuationPercentileItem]


class ScreenerStrategyParameter(BaseModel):
    key: str
    type: str
    label: str
    description: str = ""
    default: int | float | bool | str
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None


class ScreenerStrategyPreset(BaseModel):
    key: str
    name: str
    description: str
    scenario: str
    risk_level: str
    parameters: dict[str, int | float | bool | str]
    parameter_definitions: list[ScreenerStrategyParameter]


class ScreenerStrategyRequest(BaseModel):
    strategy_key: str = Field(min_length=1, max_length=64)
    version: str | None = None
    parameters: dict[str, int | float | bool | str] = Field(default_factory=dict, max_length=64)
    codes: list[str] = Field(min_length=1, max_length=200)
    lookback_days: int = Field(default=400, ge=60, le=1000)
    max_signal_age_bars: int | None = Field(default=20, ge=0, le=250)


class ScreenerStrategyMatch(BaseModel):
    code: str
    signal_date: str
    target_position: int
    signal_age_bars: int = 0
    entry_price: float | None = None
    latest_price: float | None = None
    return_since_signal_pct: float | None = None
    average_amount_20d_yi: float | None = None
    data_source: str = ""
    data_hash: str = ""
    used_fallback: bool = False


class ScreenerStrategyResult(BaseModel):
    strategy_key: str
    strategy_name: str
    strategy_version: str
    definition_hash: str
    parameters: dict[str, int | float | bool | str]
    matches: list[ScreenerStrategyMatch]
    matched_codes: list[str]
    evaluated: int
    failed: dict[str, str] = Field(default_factory=dict)
    excluded: dict[str, str] = Field(default_factory=dict)
    fallback_count: int = 0
