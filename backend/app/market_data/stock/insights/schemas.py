from pydantic import BaseModel, Field


class StockFundFlowItem(BaseModel):
    """单个交易日的个股分级资金净流入。"""

    date: str
    main_net: float | None = None
    small_net: float | None = None
    mid_net: float | None = None
    large_net: float | None = None
    super_net: float | None = None


class StockSentiment(BaseModel):
    """个股热度、排名和新闻数量汇总。"""

    code: str
    heat_score: float | None = None
    hot_rank: int | None = None
    news_count: int = 0


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
