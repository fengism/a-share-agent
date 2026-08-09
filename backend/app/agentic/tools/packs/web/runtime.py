"""Web search, fetch, and Twitter tool orchestration."""

from app.agentic.catalog import registry
from app.agentic.tools.packs.web import content, fetcher, pdf, registration, search, twitter
from app.agentic.tools.packs.web.url_security import (
    assert_url_safe,
    is_twitter_url,
)
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore

_WEB_FETCH_POLICY = registration.WEB_FETCH_POLICY
_WEB_BATCH_POLICY = registration.WEB_BATCH_POLICY
_WEB_SEARCH_POLICY = registration.WEB_SEARCH_POLICY
_TWITTER_ANALYSIS_POLICY = registration.TWITTER_ANALYSIS_POLICY

_fetch_cache = fetcher.fetch_cache

_extract_text = content.extract_text
_smart_truncate = content.smart_truncate
_http_get_with_retry = fetcher.http_get_with_retry
_detect_content_type = pdf.detect_content_type
_handle_pdf_response = pdf.handle_pdf_response


async def _fetch_tweet(url: str):
    return await twitter.fetch_tweet(url, truncate_func=_smart_truncate)


async def _scrapling_fallback(url: str):
    return await fetcher.scrapling_fallback(
        url,
        cache=_fetch_cache,
        truncate_func=_smart_truncate,
    )


async def _fetch_url(url: str):
    return await fetcher.fetch_url(
        url,
        cache=_fetch_cache,
        fetch_tweet_func=_fetch_tweet,
        is_twitter_url_func=is_twitter_url,
        assert_url_safe_func=assert_url_safe,
        http_get_func=_http_get_with_retry,
        content_type_detector=_detect_content_type,
        pdf_handler=_handle_pdf_response,
        text_extractor=_extract_text,
        fallback_func=_scrapling_fallback,
        truncate_func=_smart_truncate,
    )


async def _fetch_urls(urls: list[str]):
    return await fetcher.fetch_urls(urls, fetch_one=_fetch_url)


async def _execute_web_search(
    query: str,
    engine: search.SearchEngineName = "baidu",
    max_results: int = 5,
    time_range: search.SearchTimeRange = "half_year",
    language: search.SearchLanguage = "zh",
):
    return await search.execute_web_search(
        query,
        engine,
        max_results,
        time_range,
        language,
        call_blocking_func=call_blocking,
        semaphore=misc_semaphore,
    )


async def _execute_twitter_analyze(username: str) -> str:
    return await twitter.execute_twitter_analyze(username)


def register_web_tools() -> None:
    registration.register_web_tools(
        _fetch_url,
        _fetch_urls,
        _execute_web_search,
        target_registry=registry,
        fetch_policy=_WEB_FETCH_POLICY,
        batch_policy=_WEB_BATCH_POLICY,
        search_policy=_WEB_SEARCH_POLICY,
    )


def register_twitter_tools() -> None:
    registration.register_twitter_tools(
        _execute_twitter_analyze,
        target_registry=registry,
        policy=_TWITTER_ANALYSIS_POLICY,
    )
