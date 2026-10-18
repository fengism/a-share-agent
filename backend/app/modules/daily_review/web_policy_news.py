"""每日复盘财经政策新闻的 Web Search 补充源。"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, cast
from urllib.parse import urlsplit

from app.core.cache import analysis_cache
from app.core.news import dedupe_news_items, parse_news_datetime
from app.core.timezones import SHANGHAI_TIMEZONE
from app.domain.news import NewsSearchItem

# 同一复盘日的政策新闻搜索结果在进程内复用 6 小时：单次生成会打 3 次外部搜索，
# 同日多用户/重复生成时不必重复打。空结果不写入缓存，避免把一次超时固化 6 小时。
_POLICY_NEWS_CACHE_TTL_SECONDS = 6 * 60 * 60.0
_SEARCH_QUERIES = (
    "A股 财经 政策 央行 证监会 国务院",
    "中国 宏观经济 产业政策 行业政策 资本市场",
    "中国 房地产 楼市 购房 买房 房贷 按揭 贴息 补贴 住房政策",
)
_PUBLISHED_AT_KEYS = (
    "published_at",
    "publish_time",
    "published_time",
    "pub_date",
    "date_published",
    "date",
)


def _parse_absolute_date(value: object, target_date: date) -> datetime | None:
    reference = datetime.combine(target_date, time(23, 59, 59), tzinfo=SHANGHAI_TIMEZONE)
    parsed = parse_news_datetime(
        value,
        now=reference,
        allow_relative=False,
        allow_time_only=False,
        assume_year=True,
    )
    if parsed is not None:
        return cast(datetime, parsed)
    if isinstance(value, str):
        try:
            parsed_rfc = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            parsed_rfc = None
        if parsed_rfc is not None:
            if parsed_rfc.tzinfo is None:
                parsed_rfc = parsed_rfc.replace(tzinfo=SHANGHAI_TIMEZONE)
            return parsed_rfc.astimezone(SHANGHAI_TIMEZONE)
        for pattern in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(value.strip(), pattern).replace(tzinfo=SHANGHAI_TIMEZONE)
            except ValueError:
                continue
    return None


def _extract_absolute_date(text: str, target_date: date) -> datetime | None:
    candidates = [
        *re.findall(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?", text),
        *re.findall(r"(?<!\d)\d{8}(?!\d)", text),
        *re.findall(r"(?<!\d)\d{1,2}[-/月]\d{1,2}日?(?!\d)", text),
        *re.findall(
            r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
            r"\s+\d{1,2},?\s+\d{4}",
            text,
            flags=re.IGNORECASE,
        ),
    ]
    for candidate in candidates:
        parsed = _parse_absolute_date(candidate, target_date)
        if parsed is not None:
            return parsed
    return None


def _result_publish_time(
    result: dict[str, Any],
    target_date: date,
    *,
    url: str,
    fallback_text: str,
) -> datetime | None:
    for key in _PUBLISHED_AT_KEYS:
        value = result.get(key)
        if value in (None, ""):
            continue
        parsed = _parse_absolute_date(value, target_date)
        if parsed is not None:
            return parsed
    # 新闻标题常写政策生效日（例如“10 月 1 日起实施”），并非发布时间。
    # 官方与媒体文章 URL 通常携带归档发布日期，因此先于标题/摘要解析。
    return _extract_absolute_date(url, target_date) or _extract_absolute_date(fallback_text, target_date)


def search_results_to_news(results: list[dict[str, Any]], target_date: date) -> list[NewsSearchItem]:
    """仅接收能从标题、摘要或 URL 识别出绝对发布日期的搜索结果。"""
    items: list[NewsSearchItem] = []
    for result in results:
        title = str(result.get("title") or "").strip()
        snippet = str(result.get("snippet") or "").strip()
        url = str(result.get("url") or "").strip()
        published = _result_publish_time(
            result,
            target_date,
            url=url,
            fallback_text=f"{title} {snippet}",
        )
        if not title or published is None:
            continue
        hostname = (urlsplit(url).hostname or "").removeprefix("www.")
        engine = str(result.get("engine") or "web")
        if published.tzinfo is None:
            published = published.replace(tzinfo=SHANGHAI_TIMEZONE)
        else:
            published = published.astimezone(SHANGHAI_TIMEZONE)
        items.append(NewsSearchItem(
            title=title,
            content=snippet[:1000],
            source=f"Web Search · {hostname or engine}",
            publish_time=published.isoformat(timespec="seconds"),
            url=url,
            author="",
            read_count=0,
            comment_count=0,
            category="Web Search 财经政策",
            source_api=engine,
        ))
    return cast(list[NewsSearchItem], dedupe_news_items(items))


async def search_financial_policy_news(target_date: date) -> list[NewsSearchItem]:
    """搜索复盘日前后两天的财经政策新闻；失败时返回空列表交由质量状态展示。"""
    cache_key = f"daily_review_policy_news:{target_date.isoformat()}"
    cached = analysis_cache.get(cache_key)
    if isinstance(cached, list):
        return cast(list[NewsSearchItem], cached)
    news = await _search_financial_policy_news_uncached(target_date)
    if news:
        analysis_cache.set(cache_key, news, _POLICY_NEWS_CACHE_TTL_SECONDS)
    return news


async def _search_financial_policy_news_uncached(target_date: date) -> list[NewsSearchItem]:
    from app.agentic_integration.tools.packs.web.search import execute_web_search

    start = target_date.fromordinal(target_date.toordinal() - 2)
    end = target_date.fromordinal(target_date.toordinal() + 2)

    async def search(query: str) -> list[NewsSearchItem]:
        explicit_query = (
            f"{query} 发布时间 {start.isoformat()} 至 {end.isoformat()} "
            "site:gov.cn OR site:pbc.gov.cn OR site:csrc.gov.cn OR site:ndrc.gov.cn "
            "OR site:mohurd.gov.cn OR site:mof.gov.cn OR 财经新闻"
        )
        try:
            payload = await execute_web_search(
                explicit_query,
                engine="auto",
                max_results=10,
                time_range="any",
                language="zh",
            )
        except Exception as error:
            logging.getLogger(__name__).debug("政策新闻 Web Search 失败: %s", error)
            return []
        return search_results_to_news(cast(list[dict[str, Any]], payload.get("results") or []), target_date)

    batches = await asyncio.gather(*(search(query) for query in _SEARCH_QUERIES))
    earliest = target_date - timedelta(days=2)
    latest = target_date + timedelta(days=2)
    in_window = [
        item
        for batch in batches
        for item in batch
        if (
            published := parse_news_datetime(
                item.publish_time,
                allow_relative=False,
                allow_time_only=False,
            )
        ) is not None
        and earliest <= published.date() <= latest
    ]
    # 先过滤时间窗口再截断，避免过期搜索结果占满 20 条配额，把目标日政策挤掉。
    return cast(list[NewsSearchItem], dedupe_news_items(in_window))[:20]
