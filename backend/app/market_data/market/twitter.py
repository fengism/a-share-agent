"""Twitter 市场资讯的数据访问与刷新能力。"""

import logging

from app.configuration import get_settings
from app.contracts.search import NewsSearchItem
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.infrastructure.persistence.twitter_store import (
    TWITTER_REFRESH_INTERVAL_SECONDS,
    get_stale_authors,
    query_twitter_posts_by_authors,
    save_twitter_refresh,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)


def _get_twitter_provider():
    return get_provider("twitter")


def _serialize_posts(posts: list[NewsSearchItem]) -> list[dict]:
    return [post.model_dump() for post in posts]


async def refresh_twitter_feeds(feeds: list[str]) -> int:
    """拉取指定账号的最新内容并写入本地存储。"""
    if not feeds:
        return 0

    posts = await provider_gateway.call_blocking(
        "twitter",
        "feed_refresh",
        _get_twitter_provider().fetch_posts_for_users,
        feeds,
    )
    await call_blocking(
        save_twitter_refresh,
        feeds,
        _serialize_posts(posts),
        semaphore=database_semaphore,
    )
    return len(posts)


def refresh_twitter_feeds_sync(feeds: list[str]) -> int:
    """同步拉取指定账号的最新内容并写入本地存储。"""
    if not feeds:
        return 0

    posts = provider_gateway.call_sync(
        "twitter",
        "feed_refresh",
        lambda: _get_twitter_provider().fetch_posts_for_users(feeds),
    )
    save_twitter_refresh(feeds, _serialize_posts(posts))
    return len(posts)


async def get_twitter_feed() -> list[NewsSearchItem]:
    """从本地存储读取配置账号的最新内容。"""
    feeds = get_settings().twitter_feeds
    if not feeds:
        return []

    rows = await call_blocking(
        query_twitter_posts_by_authors,
        feeds,
        semaphore=database_semaphore,
    )
    return [NewsSearchItem(**row) for row in rows]


def get_twitter_user_articles(username: str) -> list[dict]:
    """读取指定 Twitter 用户的文章数据。"""
    return provider_gateway.call_sync(
        "twitter",
        "user_articles",
        lambda: _get_twitter_provider().fetch_user_articles_raw(username),
    )


def get_twitter_user_content(username: str, limit: int = 40) -> list[dict]:
    """读取指定账号的本地推文与长文，本地为空时同步刷新一次。"""
    rows = query_twitter_posts_by_authors([username], limit)
    if rows:
        return rows
    if username in get_stale_authors([username]):
        refresh_twitter_feeds_sync([username])
    return query_twitter_posts_by_authors([username], limit)


async def refresh_twitter_feed_now() -> dict:
    """立即刷新已超过刷新间隔的配置账号。"""
    feeds = get_settings().twitter_feeds
    if not feeds:
        return {"status": "skipped", "reason": "未配置 Twitter feeds"}

    stale = await call_blocking(
        get_stale_authors,
        feeds,
        semaphore=database_semaphore,
    )
    if not stale:
        refresh_hours = TWITTER_REFRESH_INTERVAL_SECONDS // 3600
        return {"status": "skipped", "reason": f"没有需要刷新的账号（{refresh_hours} 小时内已刷新过）"}

    logger.info("Twitter manual refresh: fetching stale authors: %s", stale)
    posts_count = await refresh_twitter_feeds(stale)
    return {"status": "ok", "authors": stale, "posts_count": posts_count}
