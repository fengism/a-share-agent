from typing import Literal

from pydantic import BaseModel


class PushRequest(BaseModel):
    """Purpose: 推送接口的请求体，支持 Notion/飞书两种目标和四种内容类型。"""
    target: Literal["notion", "feishu"]
    type: Literal["daily_review", "analysis", "chat", "industry_chain"]
    date: str = ""
    code: str = ""
    feishu_receiver: str = ""
    chat_title: str = ""
    chat_content: str = ""
    industry_name: str = ""
    archive_id: str = ""


class PushResponse(BaseModel):
    """Purpose: 推送操作的响应结果。"""
    success: bool
    target: str
    url: str = ""
    title: str = ""
    message: str = ""
