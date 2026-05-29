from pydantic import BaseModel, Field


class NewsSearchItem(BaseModel):
    title: str
    content: str
    source: str
    publish_time: str
    url: str
    author: str
    read_count: int
    comment_count: int