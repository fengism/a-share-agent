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
    industries: list[str] | None = None
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
    page_size: int = Field(default=50, ge=1, le=200)


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
    exchange: str | None = None
    board: str | None = None
    listing_date: str | None = None
    exchange_industry: str | None = None
    second_industry: StockConcept | None = None


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


class ScreenerStrategyMatch(BaseModel):
    code: str
    signal_date: str
    target_position: int
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
    fallback_count: int = 0
