import logging
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# 项目根目录（backend 的上一级）
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Purpose: 应用全局配置，从 .env 文件或环境变量加载 LLM、缓存、飞书、问财等模块的参数。"""

    model_config = SettingsConfigDict(
        env_file=[ROOT_DIR / ".env", ROOT_DIR / "backend" / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM 配置
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"
    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 180

    # 缓存配置
    cache_ttl_realtime: int = 300  # 5分钟
    cache_ttl_financial: int = 86400  # 24小时
    cache_ttl_analysis: int = 14400  # 4小时

    # 限流配置
    max_concurrent_akshare: int = 2

    # Notion 转存配置
    notion_enabled: bool = False
    notion_api_token: str = ""
    notion_parent_page_id: str = ""
    notion_database_id: str = ""

    # 飞书推送配置
    feishu_enabled: bool = True
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_folder_token: str = ""
    feishu_wiki_space_id: str = ""
    feishu_wiki_daily_review_parent: str = ""
    feishu_wiki_analysis_parent: str = ""
    feishu_daily_review_folder: str = ""
    feishu_analysis_folder: str = ""
    feishu_default_receiver: str = ""

    # 问财数据源配置
    iwencai_enabled: bool = False
    iwencai_base_url: str = "https://openapi.iwencai.com"
    iwencai_api_key: str = ""

    # HTTP 客户端配置
    # 设为 false 时，所有 requests 调用将忽略系统 HTTP_PROXY/HTTPS_PROXY 环境变量
    http_trust_env: bool = False

    # 数据源 Cookie / Token 配置（留空使用内置默认值）
    eastmoney_cookie: str = ""
    baidu_cookie: str = ""
    baidu_acs_token: str = ""
    ths_cookie: str = ""

    # 多 Agent 配置
    multi_agent_enabled: bool = True

    # Twitter 财经账号配置
    twitter_feeds: list[str] = ["qinbafrank"]
    
    # 管理端认证密钥（留空不启用鉴权）
    admin_api_key: str = ""

    @model_validator(mode="after")
    def apply_provider_defaults(self) -> "Settings":
        """根据 llm_provider 自动填充 base_url 和 model 的默认值。

        Return:
            更新后的 Settings 实例。
        """
        provider = self.llm_provider.lower()
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        default_base_url = Settings.model_fields["llm_base_url"].default
        default_model = Settings.model_fields["llm_model"].default
        if self.llm_base_url == default_base_url and "base_url" in defaults:
            self.llm_base_url = defaults["base_url"]
        if self.llm_model == default_model and "model" in defaults:
            self.llm_model = defaults["model"]
        return self


PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "GLM-4.7-Flash",
    },
}

_current_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局复用的 Settings 实例，首次调用时自动加载配置。

    Return:
        全局 Settings 单例。
    """
    global _current_settings
    if _current_settings is None:
        _current_settings = Settings()
    return _current_settings


def _mask_secret(value: str, visible: int = 4) -> str:
    """将敏感字符串中间部分掩码为星号，仅保留前 4 位和后 4 位。

    Param:
        value: 原始敏感字符串。
        visible: 保留前几位可见字符（忽略，统一保留前后4位）。
    Return:
        掩码后的字符串。
    """
    if not value or len(value) <= 8:
        if not value or len(value) <= 4:
            return value
        return value[:4] + "***"
    return value[:4] + "***" + value[-4:]


def update_settings(patch: dict) -> Settings:
    """运行时更新全局配置，支持密钥掩码识别及 provider 自动切换。

    Param:
        patch: 要更新的字段及其新值的字典。
    Return:
        更新后的 Settings 实例。
    """
    global _current_settings
    current = get_settings()

    old_provider = current.llm_provider.lower()
    old_defaults = PROVIDER_DEFAULTS.get(old_provider, {})

    for key, value in patch.items():
        if value is None or not hasattr(current, key):
            continue
        # Skip masked secrets — user didn't actually change them
        if key in ("llm_api_key", "feishu_app_secret", "iwencai_api_key", "notion_api_token", "eastmoney_cookie", "baidu_cookie", "ths_cookie") and isinstance(value, str) and value.endswith("***"):
            continue
        setattr(current, key, value)

    # If provider changed and base_url/model still match old defaults, auto-switch
    new_provider = current.llm_provider.lower()
    new_defaults = PROVIDER_DEFAULTS.get(new_provider, {})
    if new_provider != old_provider:
        if current.llm_base_url == old_defaults.get("base_url") and "base_url" in new_defaults:
            current.llm_base_url = new_defaults["base_url"]
        if current.llm_model == old_defaults.get("model") and "model" in new_defaults:
            current.llm_model = new_defaults["model"]

    # Reset feishu token cache when credentials change
    from app.adapters.feishu.client import _cached_token, _token_expires_at

    if any(k in patch for k in ("feishu_app_id", "feishu_app_secret")):
        import app.adapters.feishu.client as feishu_mod

        feishu_mod._cached_token = ""
        feishu_mod._token_expires_at = 0.0

    # Reset cached HTTP session when http_trust_env changes
    if "http_trust_env" in patch:
        from app.utils.http_client import _reset_session

        _reset_session()

    # Trigger immediate twitter fetch when account list changes (async to avoid blocking event loop)
    if "twitter_feeds" in patch:
        import asyncio

        async def _async_twitter_fetch(feeds: list[str]) -> None:
            """异步拉取 Twitter 帖子并持久化，避免阻塞事件循环。"""
            try:
                from app.services.providers.twitter import twitter_provider
                from app.db.twitter_store import save_twitter_posts

                raw = await asyncio.to_thread(twitter_provider.fetch_posts_for_users, feeds)
                await asyncio.to_thread(save_twitter_posts, [p.model_dump() for p in raw])
                logger.info(f"twitter_feeds changed, immediate fetch done: {feeds}")
            except Exception as exc:
                logger.warning(f"twitter_feeds changed, immediate fetch failed: {exc}")

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_async_twitter_fetch(current.twitter_feeds))
        except RuntimeError:
            # No running event loop (e.g. CLI usage) — run synchronously
            try:
                from app.services.providers.twitter import twitter_provider
                from app.db.twitter_store import save_twitter_posts

                raw = twitter_provider.fetch_posts_for_users(current.twitter_feeds)
                save_twitter_posts([p.model_dump() for p in raw])
                logger.info(f"twitter_feeds changed, immediate fetch done: {current.twitter_feeds}")
            except Exception as exc:
                logger.warning(f"twitter_feeds changed, immediate fetch failed: {exc}")

    return current
