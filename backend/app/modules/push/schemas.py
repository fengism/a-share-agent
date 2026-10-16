"""内容推送请求与响应模型。"""

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


class TestWebhookRequest(BaseModel):
    """Purpose: Webhook 通知通道连通性测试请求。"""
    __test__ = False
    channel: Literal["feishu", "wecom", "wxpusher", "dingtalk"]
    webhook_url: str = ""
    secret: str = ""
    uids: str = ""


class TestWebhookResponse(BaseModel):
    """Purpose: Webhook 通知通道连通性测试响应。"""
    __test__ = False
    success: bool
    channel: str
    message: str


class NotificationChannelStatus(BaseModel):
    """Purpose: 系统通知通道配置与启用状态。"""
    feishu_configured: bool
    dingtalk_configured: bool = False
    wecom_configured: bool
    wxpusher_configured: bool
    feishu_enabled: bool = True
    dingtalk_enabled: bool = True
    wecom_enabled: bool = True
    wxpusher_enabled: bool = True
    auto_enabled: bool
    daily_review_auto: bool
    potential_auto: bool
