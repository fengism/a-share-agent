from typing import Literal

from pydantic import BaseModel, Field

from app.financial_data.stock.insights.sources import (
    EASTMONEY_FUND_FLOW_API,
    EASTMONEY_FUND_FLOW_SOURCE_ID,
)


class StockFundFlowItem(BaseModel):
    """单个交易日的个股分级资金净流入。"""

    date: str
    main_net: float | None = None
    small_net: float | None = None
    mid_net: float | None = None
    large_net: float | None = None
    super_net: float | None = None
    source: str = EASTMONEY_FUND_FLOW_SOURCE_ID
    source_api: str = EASTMONEY_FUND_FLOW_API
    is_stale: bool = False


class MarginTradingItem(BaseModel):
    date: str
    rzye: float | None = None
    rzmre: float | None = None
    rzche: float | None = None
    rqye: float | None = None
    rqmcl: float | None = None
    rqchl: float | None = None
    rzrqye: float | None = None


class BlockTradeItem(BaseModel):
    date: str
    price: float | None = None
    close: float | None = None
    premium_pct: float | None = None
    vol: float | None = None
    amount: float | None = None
    buyer: str = ""
    seller: str = ""


class HolderChangeItem(BaseModel):
    date: str
    holder_num: float | None = None
    change_num: float | None = None
    change_ratio: float | None = None
    avg_shares: float | None = None


RiskSection = Literal["fund_flow", "margin_trading", "block_trade", "holder_change"]


class StockRiskData(BaseModel):
    code: str
    fund_flow: list[StockFundFlowItem] = Field(default_factory=list)
    margin_trading: list[MarginTradingItem] = Field(default_factory=list)
    block_trade: list[BlockTradeItem] = Field(default_factory=list)
    holder_change: list[HolderChangeItem] = Field(default_factory=list)
    partial: bool = False
    unavailable_sections: list[RiskSection] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)
    source_apis: dict[str, str] = Field(default_factory=dict)


class StockSentiment(BaseModel):
    """个股热度、排名和新闻数量汇总。"""

    code: str
    heat_score: float | None = None
    hot_rank: int | None = None
    news_count: int = 0
    partial: bool = False
    unavailable_sections: list[Literal["heat", "news_count"]] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)
    source_apis: dict[str, str] = Field(default_factory=dict)


class RetailSentimentPost(BaseModel):
    text: str
    author: str | None = None
    publish_time: str | None = None


class RetailSentiment(BaseModel):
    """个股散户讨论情绪汇总。"""

    code: str
    score: float | None = None
    post_count: int = 0
    bullish_ratio: float | None = None
    bearish_ratio: float | None = None
    sample_posts: list[RetailSentimentPost] = Field(default_factory=list)
    summary: str = ""
    guba_post_count: int = 0
    partial: bool = False
    unavailable_sections: list[Literal["guba_posts"]] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)
    source_apis: dict[str, str] = Field(default_factory=dict)
