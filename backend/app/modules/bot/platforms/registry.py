"""Bot 平台适配器注册表。"""

from app.configuration import get_settings
from app.configuration.schema import Settings
from app.infrastructure.http.client import get_session
from app.infrastructure.integrations.feishu.client import FeishuClient
from app.modules.bot.platforms.base import BotPlatform
from app.modules.bot.platforms.feishu import FeishuPlatform


def get_bot_feishu_settings() -> Settings:
    settings = get_settings()
    return settings.model_copy(
        update={
            "feishu_enabled": settings.bot_enabled,
            "feishu_app_id": settings.bot_feishu_app_id or settings.feishu_app_id,
            "feishu_app_secret": settings.bot_feishu_app_secret or settings.feishu_app_secret,
        }
    )


_bot_feishu_client = FeishuClient(get_bot_feishu_settings, get_session)
feishu_platform = FeishuPlatform(get_settings, client=_bot_feishu_client)


def get_bot_platform(platform_name: str) -> BotPlatform:
    if platform_name == feishu_platform.platform_name:
        return feishu_platform
    raise ValueError(f"不支持的 Bot 平台: {platform_name}")
