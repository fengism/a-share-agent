from pydantic import BaseModel, Field

from app.domain.stock import StockConcept


class StockDataSource(BaseModel):
    """基础资料使用的数据来源及上游 API。"""

    id: str
    name: str
    provider: str
    operation: str
    api: str


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
    exchange_industry: str | None = None
    first_industry: StockConcept | None = None
    second_industry: StockConcept | None = None
    third_industry: StockConcept | None = None
    current_price: float | None = None
    concepts: list[StockConcept] | None = None
    data_sources: list[StockDataSource] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)


class StockBusinessIntro(BaseModel):
    """股票主营介绍及同花顺动态字段。"""

    code: str
    source: str = "ths"
    items: dict[str, str] = Field(default_factory=dict)
