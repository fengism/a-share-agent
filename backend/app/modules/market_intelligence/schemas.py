"""市场情报分析响应模型。"""

from typing import Literal

from pydantic import BaseModel, Field


class TwitterContentItem(BaseModel):
    """Twitter 用户推文或长文摘要。"""

    title: str
    content: str
    publish_time: str
    url: str


class TwitterAnalysisReference(BaseModel):
    """支撑 Twitter 观点的原始内容引用。"""

    index: int = Field(ge=1)
    title: str = ""
    url: str = ""
    publish_time: str = ""


class TwitterAnalysisView(BaseModel):
    """Twitter 用户的一条结构化核心观点。"""

    text: str
    stance: Literal["看多", "看空", "中性"] = "中性"
    confidence: int = Field(default=0, ge=0, le=100)
    references: list[TwitterAnalysisReference] = Field(default_factory=list)


class TwitterAnalysisResult(BaseModel):
    """Twitter 用户推文与长文分析结果。"""

    username: str
    content_count: int = Field(ge=0)
    sources: list[TwitterContentItem] = Field(default_factory=list)
    article_count: int = Field(default=0, ge=0, deprecated=True)
    articles: list[TwitterContentItem] = Field(default_factory=list, deprecated=True)
    analysis: str
    summary: str = ""
    stance: Literal["看多", "看空", "中性"] = "中性"
    confidence: int = Field(default=0, ge=0, le=100)
    core_views: list[TwitterAnalysisView] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    stocks: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    generated_at: str = ""
    cache_hit: bool = False


class TwitterFeedRefreshResponse(BaseModel):
    status: Literal["ok", "skipped"]
    reason: str | None = None
    authors: list[str] = Field(default_factory=list)
    posts_count: int = Field(default=0, ge=0)


class NewsAnalysisReference(BaseModel):
    title: str = ""
    url: str


class NewsAnalysisItem(BaseModel):
    text: str
    urls: list[NewsAnalysisReference] = Field(default_factory=list)


class NewsAnalysisSection(BaseModel):
    title: str
    icon: str = ""
    items: list[NewsAnalysisItem] = Field(default_factory=list)


class NewsAnalysisResponse(BaseModel):
    market_sentiment: str = "中性"
    summary: str = ""
    sections: list[NewsAnalysisSection] = Field(default_factory=list)
