from pydantic import BaseModel

from app.contracts.stock import StockConcept


class StockBasicInfo(BaseModel):
    """股票基础信息、行业分类与当前估值概览。"""

    code: str
    name: str
    listing_date: str | None = None
    total_shares: float | None = None
    circulating_shares: float | None = None
    pe_ttm: float | None = None
    pe_static: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    float_market_cap: float | None = None
    turnover_pct: float | None = None
    first_industry: StockConcept | None = None
    second_industry: StockConcept | None = None
    current_price: float | None = None
    concepts: list[StockConcept] | None = None
