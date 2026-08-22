"""Direct in-process browser fetch for stealth and dynamic rendering."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

from app.agentic.tools.packs.web.content import extract_text
from app.agentic.tools.packs.web.url_security import UnsafeUrlError, validate_url_syntax
from app.core.metrics import metrics

logger = logging.getLogger(__name__)

BrowserMode = Literal["stealth", "dynamic"]
_MIN_CONTENT_LEN = 200
_STABILITY_POLL_SECONDS = 0.5
_BROWSER_FLAGS = ["--disable-dev-shm-usage"]
_BROWSER_CONTEXT = {
    "service_workers": "allow",
    "ignore_https_errors": False,
    "accept_downloads": False,
    "permissions": [],
}


def normalize_scrapling_logging() -> None:
    """Route Scrapling logs through the application root handler exactly once."""
    names = ["scrapling", *(
        name
        for name in logging.Logger.manager.loggerDict
        if isinstance(name, str) and name.startswith("scrapling.")
    )]
    for name in names:
        library_logger = logging.getLogger(name)
        library_logger.handlers.clear()
        library_logger.setLevel(logging.NOTSET)
        library_logger.propagate = True


@dataclass(frozen=True, slots=True)
class RenderedDocument:
    url: str
    title: str
    html: str


class BrowserConcurrencyGate:
    """Process-local dynamic concurrency gate for browser launches."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active = 0

    @asynccontextmanager
    async def slot(self, limit: int) -> AsyncIterator[float]:
        queued_at = time.perf_counter()
        async with self._condition:
            await self._condition.wait_for(lambda: self._active < max(1, limit))
            self._active += 1
            queue_wait_ms = (time.perf_counter() - queued_at) * 1000
        try:
            yield queue_wait_ms
        finally:
            async with self._condition:
                self._active = max(0, self._active - 1)
                self._condition.notify_all()


_browser_gate = BrowserConcurrencyGate()


def _load_fetchers() -> Mapping[str, Any]:
    from scrapling.fetchers import StealthyFetcher

    normalize_scrapling_logging()
    return {"stealth": StealthyFetcher}


async def _wait_for_stable_body(page: Any, settle_seconds: float) -> None:
    if settle_seconds <= 0:
        return
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settle_seconds
    previous_text: str | None = None
    while True:
        try:
            body_text = (await page.locator("body").inner_text()).strip()
        except Exception:
            body_text = ""
        if len(body_text) >= _MIN_CONTENT_LEN and body_text == previous_text:
            return
        previous_text = body_text
        remaining = deadline - loop.time()
        if remaining <= 0:
            return
        await page.wait_for_timeout(int(min(_STABILITY_POLL_SECONDS, remaining) * 1000))


async def fetch_dynamic_document(
    url: str,
    *,
    navigation_timeout_seconds: float,
    settle_seconds: float,
    playwright_factory: Callable[[], Any] | None = None,
) -> RenderedDocument:
    """Render a dynamic page until useful body text stabilizes."""
    if playwright_factory is None:
        from patchright.async_api import async_playwright

        playwright_factory = async_playwright

    manager = playwright_factory()
    browser = None
    context = None
    async with manager as playwright:
        browser = await playwright.chromium.launch(headless=True, args=list(_BROWSER_FLAGS))
        try:
            context = await browser.new_context(**_BROWSER_CONTEXT)
            try:
                page = await context.new_page()
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(navigation_timeout_seconds * 1000),
                    referer="https://www.google.com/",
                )
                await _wait_for_stable_body(page, settle_seconds)
                return RenderedDocument(
                    url=str(page.url),
                    title=await page.title(),
                    html=await page.content(),
                )
            finally:
                if context is not None:
                    await context.close()
        finally:
            if browser is not None:
                await browser.close()


def _bounded_text(text: str, max_content_bytes: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_content_bytes:
        return text, False
    return encoded[:max_content_bytes].decode("utf-8", errors="ignore"), True


def _browser_result(
    *,
    url: str,
    mode: BrowserMode,
    title: str,
    html: str,
    max_content_bytes: int,
) -> dict[str, Any]:
    meta, (html_title, content) = extract_text(html)
    content, truncated = _bounded_text(content, max_content_bytes)
    result: dict[str, Any] = {
        "url": url,
        "title": title or html_title,
        "content": content,
        "content_type": "html",
        "content_length": len(content),
        "browser_mode": mode,
    }
    if meta:
        result["meta"] = meta
    if needs_fallback(content):
        result["error"] = f"{mode} 浏览器未提取到足够正文（{len(content)} 字符）"
    if truncated:
        result["note"] = f"浏览器正文已限制为 {max_content_bytes} 字节"
    return result


async def _execute_browser_mode(
    url: str,
    mode: BrowserMode,
    *,
    fetchers: Mapping[str, Any] | None,
    timeout_seconds: float,
    max_content_bytes: int,
    dynamic_runner: Callable[..., Any],
    settle_seconds: float,
) -> dict[str, Any]:
    operation_timeout_seconds = min(timeout_seconds, 40.0)
    async with asyncio.timeout(timeout_seconds):
        if mode == "dynamic" and fetchers is None:
            document = await dynamic_runner(
                url,
                navigation_timeout_seconds=operation_timeout_seconds,
                settle_seconds=settle_seconds,
            )
            return _browser_result(
                url=document.url,
                mode=mode,
                title=document.title,
                html=document.html,
                max_content_bytes=max_content_bytes,
            )

        fetcher = (fetchers or _load_fetchers())[mode]
        normalize_scrapling_logging()
        kwargs: dict[str, Any] = {
            "headless": True,
            "disable_resources": False,
            "network_idle": True,
            "load_dom": True,
            "timeout": int(operation_timeout_seconds * 1000),
            "dns_over_https": False,
            "block_ads": False,
            "google_search": True,
            "retries": 1,
            "extra_flags": list(_BROWSER_FLAGS),
            "additional_args": dict(_BROWSER_CONTEXT),
        }
        if mode == "stealth":
            kwargs.update(block_webrtc=True, hide_canvas=True)
        page = await fetcher.async_fetch(url, **kwargs)

    html = str(getattr(page, "html_content", "") or "")
    if html:
        return _browser_result(
            url=str(getattr(page, "url", "") or url),
            mode=mode,
            title="",
            html=html,
            max_content_bytes=max_content_bytes,
        )

    text = _clean_text(page.get_all_text(" ", ignore_tags=("script", "style", "noscript")))
    text, truncated = _bounded_text(text, max_content_bytes)
    title = ""
    if hasattr(page, "css"):
        title_elements = page.css("title")
        if title_elements:
            title = (title_elements[0].text or "").strip()
    result = {
        "url": str(getattr(page, "url", "") or url),
        "title": title,
        "content": text,
        "content_type": "html",
        "content_length": len(text),
        "browser_mode": mode,
    }
    if needs_fallback(text):
        result["error"] = f"{mode} 浏览器未提取到足够正文（{len(text)} 字符）"
    if truncated:
        result["note"] = f"浏览器正文已限制为 {max_content_bytes} 字节"
    return result


async def scrapling_fetch(
    url: str,
    mode: BrowserMode,
    *,
    fetchers: Mapping[str, Any] | None = None,
    timeout_seconds: float | None = None,
    max_content_bytes: int | None = None,
    dynamic_runner: Callable[..., Any] = fetch_dynamic_document,
    browser_gate: BrowserConcurrencyGate = _browser_gate,
) -> dict[str, Any]:
    """Render one HTTP(S) page under a shared process concurrency limit."""
    from app.configuration import get_settings

    settings = get_settings()
    try:
        validate_url_syntax(url)
    except UnsafeUrlError as error:
        return {"url": url, "title": "", "content": "", "error": str(error)}
    if not settings.web_fetch_browser_enabled:
        return {"url": url, "title": "", "content": "", "error": "浏览器抓取未启用"}
    timeout_seconds = timeout_seconds or settings.web_fetch_browser_timeout_seconds
    max_content_bytes = max_content_bytes or settings.web_fetch_max_response_bytes
    if mode not in {"stealth", "dynamic"}:
        return {"url": url, "title": "", "content": "", "error": f"不支持浏览器模式: {mode}"}

    started_at = time.perf_counter()
    result: dict[str, Any]
    async with browser_gate.slot(settings.web_fetch_browser_max_concurrency) as queue_wait_ms:
        try:
            result = await _execute_browser_mode(
                url,
                mode,
                fetchers=fetchers,
                timeout_seconds=timeout_seconds,
                max_content_bytes=max_content_bytes,
                dynamic_runner=dynamic_runner,
                settle_seconds=settings.web_fetch_browser_settle_seconds,
            )
        except Exception as error:
            detail = str(error) or type(error).__name__
            logger.warning("Browser %s 抓取失败: %s", mode, detail)
            result = {"url": url, "title": "", "content": "", "error": f"{mode} 抓取失败: {detail}"}

    success = not bool(result.get("error"))
    metrics.record_browser_fetch(
        mode,
        success=success,
        duration_ms=(time.perf_counter() - started_at) * 1000,
        content_characters=len(str(result.get("content") or "")),
        queue_wait_ms=queue_wait_ms,
        error_type=None if success else str(result.get("error", "BrowserFetchError")).split(":", 1)[0],
    )
    return result


def needs_fallback(content: str) -> bool:
    return len(content) < _MIN_CONTENT_LEN


def _clean_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()
