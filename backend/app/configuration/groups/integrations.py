"""外部协同集成配置：飞书文档、多通道推送、Notion、问财。"""

from __future__ import annotations

from app.configuration.groups.base import ConfigGroup


class FeishuGroup(ConfigGroup):
    """飞书应用（文档转存 + Bot 事件回调）。"""

    PREFIX = "feishu_"

    feishu_enabled: bool = True
    # 飞书应用凭证：文档转存与 Bot 共用；旧 BOT_FEISHU_APP_* 作为回退别名保留。
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_folder_token: str = ""
    feishu_wiki_space_id: str = ""
    feishu_wiki_daily_review_parent: str = ""
    feishu_wiki_analysis_parent: str = ""
    feishu_daily_review_folder: str = ""
    feishu_analysis_folder: str = ""
    feishu_default_receiver: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""


class PushGroup(ConfigGroup):
    """自动推送与通知通道（飞书/钉钉/企微/微信服务号）。"""

    PREFIX = "push_"

    push_auto_enabled: bool = False
    push_daily_review_auto: bool = True
    push_potential_auto: bool = True
    push_feishu_enabled: bool = True
    push_dingtalk_enabled: bool = True
    push_wecom_enabled: bool = True
    push_wxpusher_enabled: bool = True
    # 以下字段名不含 push_ 前缀，嵌套视图按原名访问。
    feishu_webhook_url: str = ""
    feishu_webhook_secret: str = ""
    dingtalk_webhook_url: str = ""
    dingtalk_webhook_secret: str = ""
    wecom_webhook_url: str = ""
    wxpusher_app_token: str = ""
    wxpusher_uids: str = ""


class NotionGroup(ConfigGroup):
    """Notion 研报转存。"""

    PREFIX = "notion_"

    notion_enabled: bool = False
    notion_api_token: str = ""
    notion_parent_page_id: str = ""
    notion_database_id: str = ""


class IwencaiGroup(ConfigGroup):
    """问财自然语言选股。"""

    PREFIX = "iwencai_"

    iwencai_enabled: bool = False
    iwencai_base_url: str = "https://openapi.iwencai.com"
    iwencai_api_key: str = ""
