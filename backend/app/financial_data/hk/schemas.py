from __future__ import annotations

from pydantic import BaseModel, Field


class HKStockQuote(BaseModel):
    code: str
    name: str
    english_name: str | None = None
    trade_type: str | None = None
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    pre_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    amount: float | None = None
    bid: float | None = None
    ask: float | None = None
    updated_at: str | None = None
    pe_ttm: float | None = None
    market_cap: float | None = None
    float_market_cap: float | None = None
    pb: float | None = None
    currency: str = "HKD"


class HKStockValuation(BaseModel):
    """港股个股估值与市值指标。"""

    code: str
    name: str | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    market_cap: float | None = None
    float_market_cap: float | None = None
    total_shares: float | None = None
    circulating_shares: float | None = None
    currency: str = "HKD"


class HKStockQuotePage(BaseModel):
    items: list[HKStockQuote]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    source: str = "sina"
    updated_at: str | None = None


class HKStockSearchItem(BaseModel):
    code: str
    name: str
    english_name: str | None = None


class HKStockSearchResult(BaseModel):
    items: list[HKStockSearchItem]
