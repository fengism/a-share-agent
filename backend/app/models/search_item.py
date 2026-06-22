from pydantic import BaseModel, Field


class NewsSearchItem(BaseModel):
    """Purpose: 搜索结果中的单条新闻条目。"""
    title: str
    content: str
    source: str
    publish_time: str
    url: str
    author: str
    read_count: int
    comment_count: int
    image_url: str = ""
