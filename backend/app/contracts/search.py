from pydantic import BaseModel, Field


class NewsSearchItem(BaseModel):
    """搜索与资讯 Provider 返回的统一新闻条目。"""

    title: str
    content: str
    source: str
    publish_time: str
    url: str
    author: str
    read_count: int
    comment_count: int
    image_url: str = ""


class CategorizedStockNews(BaseModel):
    """按数据源分组的个股新闻集合。"""

    code: str
    eastmoney_news: list[NewsSearchItem] = Field(default_factory=list)
    cls_news: list[NewsSearchItem] = Field(default_factory=list)
