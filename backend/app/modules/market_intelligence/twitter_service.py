"""Twitter 市场情报异步应用服务。"""

import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.configuration import get_effective_settings
from app.configuration.schema import Settings
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.modules.market_intelligence.twitter_analyzer import (
    TWITTER_ANALYSIS_PROMPT_VERSION,
    analyze_twitter_content,
)
from app.modules.market_intelligence.twitter_input import select_twitter_content, twitter_content_hash
from app.modules.market_intelligence.twitter_presenter import (
    build_empty_twitter_analysis_result,
    build_twitter_analysis_result,
    mark_twitter_analysis_cache_hit,
)
from app.modules.market_intelligence.twitter_repository import (
    TwitterAnalysisSnapshotKey,
    TwitterAnalysisSnapshotRepository,
    TwitterContentRepository,
)

logger = logging.getLogger(__name__)

TWITTER_ANALYSIS_CACHE_TTL_SECONDS = 12 * 60 * 60
TwitterAnalyzer = Callable[[str, list[dict], Settings], Awaitable[dict]]


class TwitterAccountNotConfiguredError(ValueError):
    """请求分析的 Twitter 账号未在当前设置中启用。"""


def _resolve_configured_username(username: str, configured_accounts: list[str]) -> str:
    normalized = username.strip().removeprefix("@").lower()
    configured = {
        account.strip().removeprefix("@").lower(): account.strip().removeprefix("@")
        for account in configured_accounts
        if account.strip().removeprefix("@")
    }
    if not normalized or normalized not in configured:
        raise TwitterAccountNotConfiguredError("仅支持分析设置中已配置的 Twitter 账号")
    return configured[normalized]


class TwitterContentSource(Protocol):
    async def list_user_content(self, username: str) -> list[dict]: ...


class TwitterAnalysisSnapshotStore(Protocol):
    async def load(self, key: TwitterAnalysisSnapshotKey, *, max_age_seconds: int) -> dict | None: ...

    async def save(
        self,
        key: TwitterAnalysisSnapshotKey,
        result: dict,
        *,
        retention_seconds: int,
    ) -> None: ...


class TwitterAnalysisService:
    def __init__(
        self,
        *,
        content_repository: TwitterContentSource | None = None,
        snapshot_repository: TwitterAnalysisSnapshotStore | None = None,
        analyzer: TwitterAnalyzer = analyze_twitter_content,
        settings_loader: Callable[[], Settings] = get_effective_settings,
    ) -> None:
        self._content_repository = content_repository or TwitterContentRepository()
        self._snapshot_repository = snapshot_repository or TwitterAnalysisSnapshotRepository()
        self._analyzer = analyzer
        self._settings_loader = settings_loader
        self._singleflight: AsyncSingleFlight[dict] = AsyncSingleFlight()

    async def analyze(
        self,
        username: str,
        max_content: int = 40,
        *,
        force_refresh: bool = False,
    ) -> dict:
        settings = self._settings_loader()
        configured_username = _resolve_configured_username(username, settings.twitter_feeds)
        logger.info("开始分析 Twitter 用户内容: @%s", configured_username)
        raw_content = await self._content_repository.list_user_content(configured_username)
        sources = select_twitter_content(raw_content, max_content)
        if not sources:
            return build_empty_twitter_analysis_result(configured_username)

        snapshot_key = TwitterAnalysisSnapshotKey(
            username=configured_username,
            content_hash=twitter_content_hash(sources),
            llm_provider=str(settings.llm_provider),
            llm_model=str(settings.llm_model),
            prompt_version=TWITTER_ANALYSIS_PROMPT_VERSION,
        )

        async def load_analysis() -> dict:
            if not force_refresh:
                cached = await self._snapshot_repository.load(
                    snapshot_key,
                    max_age_seconds=TWITTER_ANALYSIS_CACHE_TTL_SECONDS,
                )
                if cached is not None:
                    logger.info("命中 Twitter 分析快照: @%s", configured_username)
                    return mark_twitter_analysis_cache_hit(cached)

            analysis = await self._analyzer(configured_username, sources, settings)
            result = build_twitter_analysis_result(configured_username, sources, analysis)
            try:
                await self._snapshot_repository.save(
                    snapshot_key,
                    result,
                    retention_seconds=TWITTER_ANALYSIS_CACHE_TTL_SECONDS,
                )
            except Exception:
                logger.warning("Twitter 分析快照写入失败，返回本次生成结果: @%s", configured_username, exc_info=True)
            return result

        singleflight_key = (snapshot_key, force_refresh)
        return await self._singleflight.do(singleflight_key, load_analysis)


twitter_analysis_service = TwitterAnalysisService()


async def analyze_twitter_user(username: str, max_content: int = 40, *, force_refresh: bool = False) -> dict:
    return await twitter_analysis_service.analyze(
        username,
        max_content,
        force_refresh=force_refresh,
    )
