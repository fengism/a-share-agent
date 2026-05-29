from typing import Literal

from pydantic import BaseModel


class PushRequest(BaseModel):
    target: Literal["notion", "feishu"]
    type: Literal["daily_review", "analysis", "chat"]
    date: str = ""
    code: str = ""
    feishu_receiver: str = ""
    chat_title: str = ""
    chat_content: str = ""


class PushResponse(BaseModel):
    success: bool
    target: str
    url: str = ""
    title: str = ""
    message: str = ""
