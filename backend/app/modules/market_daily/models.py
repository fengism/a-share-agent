"""盘后市场日行情刷新领域模型。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Market = Literal["cn", "hk"]
InstrumentType = Literal["stock", "index"]
RefreshCheckpoint = Literal["initial", "recheck"]
VerificationStatus = Literal["provisional", "confirmed"]


class MarketDailyBarRecord(BaseModel):
    """一只证券在一个交易日的未复权官方收盘口径快照。"""

    market: Market
    instrument_type: InstrumentType
    code: str
    name: str = ""
    trade_date: date
    currency: Literal["CNY", "HKD"]
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float = Field(gt=0)
    pre_close: float | None = None
    change_amount: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    amount: float | None = None
    # 日行情始终保留交易所原始（未复权）价格；复权信息独立存储。
    adjustment: Literal["none"] = "none"
    source: str
    source_quote_time: datetime | None = None

    @model_validator(mode="after")
    def validate_market_values(self) -> "MarketDailyBarRecord":
        expected_currency = "CNY" if self.market == "cn" else "HKD"
        if self.currency != expected_currency:
            raise ValueError(f"{self.market} 市场币种必须为 {expected_currency}")
        if self.volume is not None and self.volume < 0:
            raise ValueError("volume 不能为负数")
        if self.amount is not None and self.amount < 0:
            raise ValueError("amount 不能为负数")
        if self.open is not None and self.open <= 0:
            raise ValueError("open 必须大于 0")
        if self.high is not None and self.high < max(self.close, self.open or self.close):
            raise ValueError("high 不能低于 close/open")
        if self.low is not None and self.low > min(self.close, self.open or self.close):
            raise ValueError("low 不能高于 close/open")
        if self.high is not None and self.low is not None and self.high < self.low:
            raise ValueError("high 不能低于 low")
        return self


class MarketCorporateAction(BaseModel):
    market: Literal["cn"] = "cn"
    code: str
    action_date: date
    sequence: int = Field(ge=0)
    category: int
    category_name: str = ""
    cash_dividend: float = 0.0
    rights_shares: float = 0.0
    rights_price: float = 0.0
    bonus_shares: float = 0.0
    split_ratio: float = 0.0
    raw_json: str
    source: str = "tdxhub.xdxr"


class MarketDailyAdjustmentFactor(BaseModel):
    market: Literal["cn"] = "cn"
    code: str
    trade_date: date
    qfq_multiplier: float
    qfq_offset: float
    hfq_multiplier: float
    hfq_offset: float
    action_hash: str
    algorithm_version: str
    source: str = "tdxhub.gbbq.adjustment_factors"
    calculated_at: datetime


class CollectedMarketDailyBars(BaseModel):
    """一个市场分区的一次完整刷新结果。"""

    segment: str
    trade_date: date
    source: str
    records: list[MarketDailyBarRecord] = Field(default_factory=list)
    no_session: bool = False
    note: str = ""


class MarketDailyBar(MarketDailyBarRecord):
    verification_status: VerificationStatus
    revision: int = Field(ge=1)
    first_refreshed_at: datetime
    last_refreshed_at: datetime


class MarketDailyBarPage(BaseModel):
    items: list[MarketDailyBar]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    trade_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    next_cursor: str | None = None


class MarketDailyBarRefreshStatus(BaseModel):
    trade_date: date
    checkpoint: RefreshCheckpoint
    segment: str
    status: Literal["pending", "running", "success", "skipped", "failed"]
    attempts: int = Field(ge=0)
    next_retry_at: datetime | None = None
    expected_count: int | None = None
    stored_count: int | None = None
    last_error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


MarketDailySegment = Literal["cn_stock", "cn_index", "hk_stock", "hk_index"]


class MarketDailyBarRefreshRequest(BaseModel):
    trade_date: date
    checkpoint: RefreshCheckpoint = "recheck"
    segments: list[MarketDailySegment] = Field(default_factory=list)
    retry_failed_only: bool = False
    force: bool = False


class MarketDailyBarRefreshResult(BaseModel):
    trade_date: date
    checkpoint: RefreshCheckpoint
    requested_segments: list[MarketDailySegment]
    statuses: list[MarketDailyBarRefreshStatus]


class MarketDailyBarRefreshHistory(BaseModel):
    items: list[MarketDailyBarRefreshStatus]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class MarketDailyBarDeleteRequest(BaseModel):
    trade_date: date
    segments: list[MarketDailySegment] = Field(default_factory=list)
    rebuild: bool = False
    checkpoint: RefreshCheckpoint = "recheck"


class MarketDailyBarDeleteResult(BaseModel):
    trade_date: date
    deleted_bars: int = Field(ge=0)
    deleted_observations: int = Field(ge=0)
    deleted_jobs: int = Field(ge=0)
    rebuild_result: MarketDailyBarRefreshResult | None = None


class MarketAdjustmentFactorStatus(BaseModel):
    code: str
    status: Literal["missing", "healthy", "stale", "degraded", "incomplete"]
    bar_count: int = Field(ge=0)
    factor_count: int = Field(ge=0)
    action_count: int = Field(ge=0)
    first_bar_date: date | None = None
    last_bar_date: date | None = None
    first_factor_date: date | None = None
    last_factor_date: date | None = None
    action_hash: str | None = None
    algorithm_version: str | None = None
    source: str | None = None
    calculated_at: datetime | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None
    using_last_good: bool = False
    coverage_complete: bool = False


class MarketAdjustmentFactorRefreshRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)
    force: bool = True


class MarketAdjustmentFactorInvalidateRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)
