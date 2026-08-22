"""全局配置更新后需要执行的基础设施副作用。"""

import asyncio
import logging

from app.configuration.schema import Settings
from app.financial_data.market.public import refresh_twitter_feeds, refresh_twitter_feeds_sync
from app.infrastructure.http.client import reset_session
from app.infrastructure.integrations.feishu.auth import clear_token_cache

logger = logging.getLogger(__name__)

_twitter_refresh_task: asyncio.Task[None] | None = None
_pending_twitter_feeds: list[str] | None = None


async def _fetch_twitter_posts(feeds: list[str]) -> None:
    try:
        await refresh_twitter_feeds(feeds)
        logger.info("twitter_feeds changed, immediate fetch done: %s", feeds)
    except Exception:
        logger.warning("twitter_feeds changed, immediate fetch failed", exc_info=True)


def _fetch_twitter_posts_sync(feeds: list[str]) -> None:
    try:
        refresh_twitter_feeds_sync(feeds)
        logger.info("twitter_feeds changed, immediate fetch done: %s", feeds)
    except Exception:
        logger.warning("twitter_feeds changed, immediate fetch failed", exc_info=True)


async def _run_twitter_refresh_worker() -> None:
    global _pending_twitter_feeds, _twitter_refresh_task

    current_task = asyncio.current_task()
    try:
        while _pending_twitter_feeds is not None:
            feeds = _pending_twitter_feeds
            _pending_twitter_feeds = None
            await _fetch_twitter_posts(feeds)
    finally:
        if _twitter_refresh_task is current_task:
            _twitter_refresh_task = None


def _schedule_twitter_refresh(loop: asyncio.AbstractEventLoop, feeds: list[str]) -> None:
    global _pending_twitter_feeds, _twitter_refresh_task

    _pending_twitter_feeds = list(feeds)
    if _twitter_refresh_task is None or _twitter_refresh_task.done():
        _twitter_refresh_task = loop.create_task(
            _run_twitter_refresh_worker(),
            name="settings_twitter_refresh",
        )


async def shutdown_update_side_effects() -> None:
    global _pending_twitter_feeds, _twitter_refresh_task

    _pending_twitter_feeds = None
    task = _twitter_refresh_task
    if task is None:
        return
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    if _twitter_refresh_task is task:
        _twitter_refresh_task = None


def apply_update_side_effects(updated: Settings, patch: dict) -> None:
    """清理受全局配置更新影响的缓存，并触发必要的数据刷新。"""
    if any(
        key in patch
        for key in (
            "feishu_app_id",
            "feishu_app_secret",
            "bot_feishu_app_id",
            "bot_feishu_app_secret",
        )
    ):
        clear_token_cache()

    if "http_trust_env" in patch:
        reset_session()

    if "twitter_feeds" not in patch:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _fetch_twitter_posts_sync(updated.twitter_feeds)
    else:
        _schedule_twitter_refresh(loop, updated.twitter_feeds)
