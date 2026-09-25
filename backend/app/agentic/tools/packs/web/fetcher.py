import asyncio
import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal, TypeVar, cast
from urllib.parse import urljoin, urlparse

import requests

from app.agentic.tools.packs.web.content import extract_text, smart_truncate
from app.agentic.tools.packs.web.pdf import detect_content_type, handle_pdf_response
from app.agentic.tools.packs.web.quality import body_quality_reason, checked_body, decode_html_response
from app.agentic.tools.packs.web.scrapling import BrowserMode, is_challenge_page, needs_fallback, scrapling_fetch
from app.agentic.tools.packs.web.transport import request_pinned
from app.agentic.tools.packs.web.twitter import fetch_tweet
from app.agentic.tools.packs.web.url_security import (
    ResolvedUrlTarget,
    UnsafeUrlError,
    is_twitter_url,
    resolve_url_target,
)
from app.constants.http import USER_AGENTS
from app.core.cache import TTLCache
from app.core.cache_policies import AGENT_WEB_FETCH
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.errors import log_internal_error
from app.core.metrics import metrics

logger = logging.getLogger(__name__)

T = TypeVar("T")

FETCH_CACHE_TTL = AGENT_WEB_FETCH.ttl_seconds
_BROWSER_TIMEOUT_CLEANUP_SECONDS = 5.0
MAX_REDIRECTS = 5
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
fetch_cache = TTLCache(maxsize=256, name="agent_web_fetch")
_browser_singleflight: AsyncSingleFlight[dict[str, Any]] = AsyncSingleFlight()


async def http_get_with_retry(
    url: str,
    headers: dict[str, str],
    timeout: int | float = 15,
    *,
    max_response_bytes: int | None = None,
    target_resolver: Callable[[str], ResolvedUrlTarget] = resolve_url_target,
    pinned_request: Callable[..., requests.Response] = request_pinned,
) -> requests.Response:
    """Fetch a URL with one deadline, off-loop DNS, and pinned redirect hops."""
    if max_response_bytes is None:
        from app.configuration import get_settings

        max_response_bytes = get_settings().web_fetch_max_response_bytes
    loop = asyncio.get_running_loop()
    deadline = loop.time() + float(timeout)
    current_url = url
    redirect_history: list[requests.Response] = []

    def remaining_seconds() -> float:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError(f"Web 抓取总超时: {url}")
        return remaining

    async def within_deadline(awaitable: Awaitable[T]) -> T:
        try:
            return await asyncio.wait_for(awaitable, timeout=remaining_seconds())
        except TimeoutError as error:
            raise TimeoutError(f"Web 抓取总超时: {url}") from error

    for redirect_count in range(MAX_REDIRECTS + 1):
        target = await within_deadline(asyncio.to_thread(target_resolver, current_url))
        response: requests.Response | None = None
        last_error: requests.RequestException | None = None
        for address in target.addresses:
            try:
                request_timeout = remaining_seconds()
                response = await within_deadline(
                    asyncio.to_thread(
                        pinned_request,
                        current_url,
                        target,
                        address,
                        headers=headers,
                        timeout=request_timeout,
                        allow_redirects=False,
                        max_response_bytes=max_response_bytes,
                    )
                )
                break
            except requests.RequestException as error:
                last_error = error
        if response is None:
            if last_error is not None:
                raise last_error
            raise RuntimeError(f"无法连接已验证地址: {current_url}")

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
        target_url = urljoin(redirect_url, str(location))
        target_host = (urlparse(target_url).hostname or "").lower()
        if target_host and target_host != requested_host:
            return target_url
        current_url = target_url
    return str(getattr(response, "url", "") or current_url)


FetchMode = Literal["auto", "http", "stealth", "dynamic"]
BrowserFetch = Callable[[str, BrowserMode], Awaitable[dict[str, Any]]]


def _checked_browser_result(result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("error") and is_challenge_page(title=str(result.get("title") or ""), content=str(result.get("content") or "")):
        return {"url": result.get("url", ""), "content": "", "error": "浏览器返回访问验证页，未取得正文", "error_reason": "web_challenge"}
    return checked_body(result)


async def scrapling_fallback(
    url: str,
    *,
    fetch_func: BrowserFetch = scrapling_fetch,
    browser_modes: tuple[BrowserMode, ...] = ("dynamic", "stealth"),
) -> dict[str, Any]:
    """Try browser modes in order, rejecting challenge pages as failed attempts."""
    errors: list[str] = []
    last_reason = "web_browser_failed"
    for browser_mode in browser_modes:
        metrics.record_agentic_event(f"browser_fallback_{browser_mode}")
        result = _checked_browser_result(await fetch_func(url, browser_mode))
        challenge = is_challenge_page(
            title=str(result.get("title") or ""),
            content=str(result.get("content") or ""),
        )
        if not result.get("error") and result.get("content") and not challenge:
            return result
        error = result.get("error") or (
            f"{browser_mode} 返回了访问验证页" if challenge else f"{browser_mode} 未返回正文"
        )
        errors.append(str(error))
        last_reason = result.get("error_reason") or "web_browser_failed"
    return {
        "url": url,
        "title": "",
        "content": "",
        "error": "; ".join(errors) or "浏览器抓取失败",
        "error_reason": last_reason,
    }


async def web_fetch(
    url: str,
    mode: FetchMode = "auto",
    *,
    cache: TTLCache = fetch_cache,
    fetch_tweet_func: Callable[[str], Awaitable[dict[str, Any]]] = fetch_tweet,
    is_twitter_url_func: Callable[[str], bool] = is_twitter_url,
    http_get_func: Callable[..., Awaitable[Any]] = http_get_with_retry,
    browser_fetch_func: BrowserFetch = scrapling_fetch,
    browser_timeout_seconds: float | None = None,
    content_type_detector: Callable[[str | None], str] = detect_content_type,
    pdf_handler: Callable[[Any, str], dict[str, Any]] = handle_pdf_response,
    text_extractor: Callable[[str], tuple[dict[str, str], tuple[str, str]]] = extract_text,
    fallback_func: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    truncate_func: Callable[[str], tuple[str, bool]] = smart_truncate,
) -> dict[str, Any]:
    """Fetch one URL using explicit HTTP/browser mode or guarded automatic fallback."""
    if mode not in {"auto", "http", "stealth", "dynamic"}:
        return {"url": url, "title": "", "content": "", "error": f"不支持抓取模式: {mode}"}
    cache_key = f"fetch:v2:{mode}:{url}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cast(dict[str, Any], cached)
    if is_twitter_url_func(url):
        tweet_result = await fetch_tweet_func(url)
        cache.set(cache_key, tweet_result, FETCH_CACHE_TTL)
        return tweet_result

    if browser_timeout_seconds is None:
        from app.configuration import get_settings

        browser_timeout_seconds = get_settings().web_fetch_browser_timeout_seconds
    loop = asyncio.get_running_loop()
    browser_deadline: float | None = None

    def remaining_browser_seconds() -> float:
        nonlocal browser_deadline
        if browser_deadline is None:
            browser_deadline = loop.time() + browser_timeout_seconds
        remaining = browser_deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError("浏览器抓取总超时")
        return remaining

    async def within_browser_budget(awaitable: Awaitable[T]) -> T:
        task = asyncio.ensure_future(awaitable)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=remaining_browser_seconds())
        except TimeoutError as error:
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=_BROWSER_TIMEOUT_CLEANUP_SECONDS,
                )
            except BaseException:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            raise TimeoutError("浏览器抓取总超时") from error

    async def execute_browser(target_url: str, browser_mode: BrowserMode) -> dict[str, Any]:
        metrics.record_agentic_event("browser_fetch_requested")

        async def load() -> dict[str, Any]:
            metrics.record_agentic_event("browser_fetch_executed")
            return await browser_fetch_func(target_url, browser_mode)

        return cast(dict[str, Any], await _browser_singleflight.do((target_url, browser_mode), load))

    async def reject_unsafe_browser_target(target_url: str) -> dict[str, Any] | None:
        """浏览器路径不做连接级 SSRF 校验，入口统一补 DNS→公网地址检查。

        HTTP 路径被 SSRF 防护拒绝的内网域名，不允许借道浏览器 fallback 渲染。
        """
        try:
            await asyncio.to_thread(resolve_url_target, target_url)
        except UnsafeUrlError as error:
            logger.warning("浏览器抓取拒绝不安全 URL %s: %s", target_url, error)
            return {"url": target_url, "title": "", "content": "", "error": str(error)}
        return None

    async def run_browser_fallback(
        target_url: str,
        *,
        browser_modes: tuple[BrowserMode, ...] = ("dynamic", "stealth"),
    ) -> dict[str, Any]:
        started = loop.time()
        result: dict[str, Any] | None = None
        outcome = "exception"
        try:
            unsafe_response = await reject_unsafe_browser_target(target_url)
            if unsafe_response is not None:
                result = unsafe_response
                outcome = "unsafe_url"
                return result
            try:
                if fallback_func is not None:
                    result = _checked_browser_result(await within_browser_budget(fallback_func(target_url)))
                else:
                    result = await within_browser_budget(
                        scrapling_fallback(target_url, fetch_func=execute_browser, browser_modes=browser_modes)
                    )
            except TimeoutError:
                result = {"url": target_url, "title": "", "content": "", "error": "浏览器抓取总超时", "error_reason": "web_browser_timeout"}
            reason = str(result.get("error_reason") or "")
            outcome = (reason if reason in {
                "web_browser_timeout", "web_empty_body", "web_insufficient_body",
                "web_unreadable_body", "web_script_shell", "web_challenge",
            } else "failed") if result.get("error") else "usable"
            return result
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        finally:
            # Only an opaque URL hash and host: no query tokens, page body or upstream errors.
            selected_mode = (result or {}).get("fetch_mode", "")
            logger.info(
                "浏览器回退结束: host=%s url_id=%s modes=%s selected_mode=%s outcome=%s characters=%d elapsed_ms=%d",
                urlparse(target_url).hostname or "unknown",
                hashlib.sha256(target_url.encode()).hexdigest()[:12],
                ",".join(browser_modes), selected_mode if selected_mode in {"dynamic", "stealth"} else "unknown",
                outcome, len(str((result or {}).get("content") or "")),
                round((loop.time() - started) * 1000),
            )

    if mode in {"stealth", "dynamic"}:
        unsafe_response = await reject_unsafe_browser_target(url)
        if unsafe_response is not None:
            return unsafe_response
        try:
            browser_result = _checked_browser_result(await within_browser_budget(execute_browser(url, cast(BrowserMode, mode))))
        except TimeoutError as error:
            return {"url": url, "title": "", "content": "", "error": str(error)}
        if not browser_result.get("error"):
            cache.set(cache_key, browser_result, FETCH_CACHE_TTL)
        return browser_result

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        http_request = http_get_func(url, headers=headers, timeout=15)
        response = await http_request
        resolved_url = str(getattr(response, "url", "") or url)
        content_type = content_type_detector(response.headers.get("content-type"))
        if content_type == "pdf":
            # PDF 解析是 CPU 密集的同步调用，放线程池避免阻塞事件循环
            pdf_result = await asyncio.to_thread(pdf_handler, response, resolved_url)
            if not pdf_result.get("error"):
                cache.set(cache_key, pdf_result, FETCH_CACHE_TTL)
            return pdf_result
        html = decode_html_response(response)
        meta, (title, content) = text_extractor(html)
    except UnsafeUrlError as error:
        logger.warning("拒绝抓取不安全 URL %s: %s", url, error)
        return {"url": url, "title": "", "content": "", "error": str(error)}
    except Exception as error:
        if mode == "http":
            return {"url": url, "title": "", "content": "", "error": str(error) or type(error).__name__}
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        if status_code in {404, 410}:
            return {
                "url": str(getattr(getattr(error, "response", None), "url", "") or url),
                "title": "",
                "content": "",
                "error": str(error) or f"HTTP {status_code}",
                "status_code": status_code,
            }
        logger.info("安全 HTTP 抓取失败，尝试浏览器模式: host=%s url_id=%s error_type=%s",
                    urlparse(url).hostname, hashlib.sha256(url.encode()).hexdigest()[:12], type(error).__name__)
        fallback_result = await run_browser_fallback(url)
        if not fallback_result.get("error"):
            cache.set(cache_key, fallback_result, FETCH_CACHE_TTL)
            return fallback_result
        return {
            "url": url,
            "title": "",
            "content": "",
            "error": str(error) or type(error).__name__,
            "note": str(fallback_result["error"]),
        }

    fallback_note = ""
    challenge_page = is_challenge_page(html=html, title=title, content=content)
    if challenge_page and mode == "http":
        return {
            "url": resolved_url,
            "title": title,
            "content": "",
            "error": "HTTP 抓取返回了访问验证页",
            "content_type": content_type,
            "fetch_mode": "http",
        }
    quality_reason = body_quality_reason(content)
    if mode == "auto" and (challenge_page or quality_reason or needs_fallback(content)):
        # When HTTP lands on an interstitial, restart browser navigation from the
        # caller's URL instead of opening the temporary verification endpoint.
        fallback_url = url if challenge_page else _fallback_target_url(url, response)
        explicit_waf = "cf_app_waf" in f"{html[:8192]}\n{content[:4096]}".lower()
        browser_modes: tuple[BrowserMode, ...] = ("stealth", "dynamic") if explicit_waf else ("dynamic", "stealth")
        logger.info("安全 HTTP 正文不可用 (%d 字)，尝试浏览器模式: host=%s url_id=%s",
                    len(content), urlparse(fallback_url).hostname, hashlib.sha256(fallback_url.encode()).hexdigest()[:12])
        fallback_result = await run_browser_fallback(fallback_url, browser_modes=browser_modes)
        if not fallback_result.get("error"):
            cache.set(cache_key, fallback_result, FETCH_CACHE_TTL)
            return fallback_result
        fallback_note = str(fallback_result.get("error") or "浏览器降级不可用")
        if challenge_page:
            return {
                "url": resolved_url,
                "title": title,
                "content": "",
                "error": "访问验证页，浏览器抓取未能获取正文",
                "note": fallback_note,
                "content_type": content_type,
            }

    if quality_reason:
        return checked_body({"url": resolved_url, "title": title, "content": content, "content_type": content_type, "fetch_mode": "http"})

    truncated_content, was_truncated = truncate_func(content)
    final_result: dict[str, Any] = {
        "url": resolved_url,
        "title": title,
        "content": truncated_content,
        "content_type": content_type,
        "content_length": len(content),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fetch_mode": "http",
        "body_quality": "usable",
    }
    if meta:
        final_result["meta"] = meta
    notes = []
    if was_truncated:
        notes.append(f"内容已截断至 {len(truncated_content)} 字符（原文 {len(content)} 字符）")
    if fallback_note:
        notes.append(f"已保留安全 HTTP 抓取结果；{fallback_note}")
    if notes:
        final_result["note"] = "；".join(notes)
    cache.set(cache_key, final_result, FETCH_CACHE_TTL)
    return final_result


async def fetch_urls(
    urls: list[str],
    mode: FetchMode = "auto",
    *,
    fetch_one: Callable[..., Awaitable[dict[str, Any]]] = web_fetch,
) -> list[dict[str, Any]]:
    """Fetch up to ten URLs with bounded per-batch concurrency and stable ordering."""
    if not urls:
        return []
    selected_urls = urls[:10]
    semaphore = asyncio.Semaphore(2)

    async def fetch_limited(target_url: str) -> dict[str, Any]:
        async with semaphore:
            return await fetch_one(target_url, mode=mode)

    fetched = await asyncio.gather(
        *(fetch_limited(target_url) for target_url in selected_urls),
        return_exceptions=True,
    )
    results: list[dict[str, Any]] = []
    for target_url, result in zip(selected_urls, fetched):
        if isinstance(result, BaseException):
            if not isinstance(result, Exception):
                raise result
            _, detail = log_internal_error(
                logger,
                f"批量抓取 URL {target_url}",
                result,
                "URL 抓取失败",
            )
            results.append({"url": target_url, "title": "", "content": "", "error": detail})
            continue
        results.append(result)
    return results
