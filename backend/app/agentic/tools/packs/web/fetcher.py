import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin, urlparse

import requests

from app.agentic.tools.packs.web.content import extract_text, smart_truncate
from app.agentic.tools.packs.web.pdf import detect_content_type, handle_pdf_response
from app.agentic.tools.packs.web.scrapling import needs_fallback, scrapling_fetch
from app.agentic.tools.packs.web.twitter import fetch_tweet
from app.agentic.tools.packs.web.url_security import (
    UnsafeUrlError,
    assert_url_safe,
    is_twitter_url,
)
from app.constants.http import USER_AGENTS
from app.core.cache import TTLCache
from app.core.errors import log_internal_error

logger = logging.getLogger(__name__)

FETCH_CACHE_TTL = 600
MAX_REDIRECTS = 5
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
fetch_cache = TTLCache()


async def http_get_with_retry(
    url: str,
    headers: dict,
    timeout: int = 15,
    *,
    url_validator: Callable[[str], None] = assert_url_safe,
) -> requests.Response:
    """Run a blocking HTTP GET and validate every redirect target."""
    from app.infrastructure.http.client import get as http_get

    current_url = url
    redirect_history: list[requests.Response] = []
    for redirect_count in range(MAX_REDIRECTS + 1):
        url_validator(current_url)
        response = await asyncio.to_thread(
            http_get,
            current_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
        if response.status_code not in REDIRECT_STATUS_CODES:
            response.raise_for_status()
            response.history = redirect_history
            return response

        location = response.headers.get("Location")
        if not location:
            raise RuntimeError(f"重定向响应缺少 Location: {current_url}")
        if redirect_count >= MAX_REDIRECTS:
            raise RuntimeError(f"重定向次数超过上限 {MAX_REDIRECTS}: {url}")
        redirect_history.append(response)
        current_url = urljoin(current_url, location)

    raise RuntimeError(f"无法完成 URL 抓取: {url}")


def _fallback_target_url(requested_url: str, response: Any) -> str:
    """Prefer the first cross-host redirect over an intermediary or challenge page."""
    requested_host = (urlparse(requested_url).hostname or "").lower()
    current_url = requested_url
    for redirect_response in getattr(response, "history", ()):
        redirect_url = str(getattr(redirect_response, "url", "") or current_url)
        location = redirect_response.headers.get("Location")
        if not location:
            continue
        target_url = urljoin(redirect_url, location)
        target_host = (urlparse(target_url).hostname or "").lower()
        if target_host and target_host != requested_host:
            return target_url
        current_url = target_url
    return str(getattr(response, "url", "") or current_url)


async def scrapling_fallback(
    url: str,
    *,
    cache: TTLCache = fetch_cache,
    truncate_func: Callable[[str], tuple[str, bool]] = smart_truncate,
    allowed_hosts: frozenset[str] | None = None,
    dynamic_enabled: bool | None = None,
    fetch_func: Callable[[str, str], Awaitable[dict[str, Any]]] = scrapling_fetch,
    assert_url_safe_func: Callable[[str], None] = assert_url_safe,
) -> dict[str, Any]:
    """Try Scrapling HTTP, stealth, then dynamic modes."""
    if allowed_hosts is None or dynamic_enabled is None:
        from app.configuration import get_settings

        settings = get_settings()
        if allowed_hosts is None:
            allowed_hosts = frozenset(
                host.strip().lower()
                for host in settings.web_fetch_scrapling_allowed_hosts.split(",")
                if host.strip()
            )
        if dynamic_enabled is None:
            dynamic_enabled = settings.web_fetch_scrapling_dynamic_enabled

    host = (urlparse(url).hostname or "").lower()
    if host not in allowed_hosts:
        return {
            "url": url,
            "title": "",
            "content": "",
            "error": "Scrapling 降级抓取未允许该主机",
        }

    modes = ("http", "stealth", "dynamic") if dynamic_enabled else ("http", "stealth")
    for mode in modes:
        result = await fetch_func(url, mode)
        if result.get("error"):
            logger.info("Scrapling %s 模式失败: %s", mode, result["error"])
            continue
        final_url = str(result.get("url") or url)
        final_host = (urlparse(final_url).hostname or "").lower()
        if final_host not in allowed_hosts:
            logger.warning("Scrapling 跳转到未授权主机: %s -> %s", url, final_url)
            continue
        try:
            assert_url_safe_func(final_url)
        except UnsafeUrlError as error:
            logger.warning("Scrapling 最终 URL 不安全: %s", error)
            continue
        content = result.get("content", "")
        if needs_fallback(content):
            continue

        truncated_content, was_truncated = truncate_func(content)
        result.update(
            content=truncated_content,
            content_type="html",
            content_length=len(content),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
        if was_truncated:
            result["note"] = (
                f"内容已截断至 {len(truncated_content)} 字符（原文 {len(content)} 字符）"
            )
        cache.set(f"fetch:{url}", result, FETCH_CACHE_TTL)
        return result
    return {
        "url": url,
        "title": "",
        "content": "",
        "error": "所有抓取模式均失败，请检查 URL 是否有效",
    }


async def fetch_url(
    url: str,
    *,
    cache: TTLCache = fetch_cache,
    fetch_tweet_func: Callable[[str], Awaitable[dict[str, Any]]] = fetch_tweet,
    is_twitter_url_func: Callable[[str], bool] = is_twitter_url,
    assert_url_safe_func: Callable[[str], None] = assert_url_safe,
    http_get_func: Callable[..., Awaitable[Any]] = http_get_with_retry,
    content_type_detector: Callable[[str | None], str] = detect_content_type,
    pdf_handler: Callable[[Any, str], dict[str, Any]] = handle_pdf_response,
    text_extractor: Callable[[str], tuple[dict[str, str], tuple[str, str]]] = extract_text,
    fallback_func: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    truncate_func: Callable[[str], tuple[str, bool]] = smart_truncate,
) -> dict[str, Any]:
    """Fetch one URL with SSRF checks, caching, extraction, and fallback."""
    cached = cache.get(f"fetch:{url}")
    if cached is not None:
        return cached
    if is_twitter_url_func(url):
        return await fetch_tweet_func(url)
    try:
        assert_url_safe_func(url)
    except UnsafeUrlError as error:
        logger.warning("拒绝抓取不安全 URL %s: %s", url, error)
        return {"url": url, "title": "", "content": "", "error": str(error)}

    if fallback_func is None:
        async def fallback_func(target_url: str) -> dict[str, Any]:
            return await scrapling_fallback(target_url, cache=cache, truncate_func=truncate_func)

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        response = await http_get_func(url, headers=headers, timeout=15)
        resolved_url = str(getattr(response, "url", "") or url)
        assert_url_safe_func(resolved_url)
        content_type = content_type_detector(response.headers.get("content-type"))
        response.encoding = response.apparent_encoding or "utf-8"
        if content_type == "pdf":
            result = pdf_handler(response, resolved_url)
            cache.set(f"fetch:{url}", result, FETCH_CACHE_TTL)
            return result
        meta, (title, content) = text_extractor(response.text)
    except UnsafeUrlError as error:
        logger.warning("拒绝跟随不安全重定向 %s: %s", url, error)
        return {"url": url, "title": "", "content": "", "error": str(error)}
    except Exception as error:
        logger.info("http_get 抓取失败 (%s)，尝试 Scrapling 降级: %s", url, error)
        return await fallback_func(url)

    if needs_fallback(content):
        fallback_url = _fallback_target_url(url, response)
        try:
            assert_url_safe_func(fallback_url)
        except UnsafeUrlError as error:
            logger.warning("拒绝通过 Scrapling 抓取不安全 URL %s: %s", fallback_url, error)
            return {"url": fallback_url, "title": "", "content": "", "error": str(error)}
        logger.info("内容过少 (%d 字)，尝试 Scrapling 降级: %s", len(content), fallback_url)
        result = await fallback_func(fallback_url)
        if not result.get("error"):
            cache.set(f"fetch:{url}", result, FETCH_CACHE_TTL)
        return result

    truncated_content, was_truncated = truncate_func(content)
    result: dict[str, Any] = {
        "url": resolved_url,
        "title": title,
        "content": truncated_content,
        "content_type": content_type,
        "content_length": len(content),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    if meta:
        result["meta"] = meta
    if was_truncated:
        result["note"] = (
            f"内容已截断至 {len(truncated_content)} 字符（原文 {len(content)} 字符）"
        )
    cache.set(f"fetch:{url}", result, FETCH_CACHE_TTL)
    return result


async def fetch_urls(
    urls: list[str],
    *,
    fetch_one: Callable[[str], Awaitable[dict[str, Any]]] = fetch_url,
) -> list[dict[str, Any]]:
    """Fetch up to ten URLs concurrently while preserving input order."""
    if not urls:
        return []
    selected_urls = urls[:10]
    fetched = await asyncio.gather(
        *(fetch_one(url) for url in selected_urls),
        return_exceptions=True,
    )
    results: list[dict[str, Any]] = []
    for url, result in zip(selected_urls, fetched):
        if isinstance(result, BaseException):
            if not isinstance(result, Exception):
                raise result
            _, detail = log_internal_error(
                logger,
                f"批量抓取 URL {url}",
                result,
                "URL 抓取失败",
            )
            results.append(
                {
                    "url": url,
                    "title": "",
                    "content": "",
                    "error": detail,
                }
            )
            continue
        results.append(result)
    return results
