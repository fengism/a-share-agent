"""Direct in-process browser fetch for stealth and dynamic rendering."""

from __future__ import annotations

import asyncio
import html as html_lib
import logging
import re
import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

from app.agentic.tools.packs.web.browser_proxy import (
    BrowserProxyLimits,
    BrowserResourceLimitError,
    SafeBrowserProxy,
)
from app.agentic.tools.packs.web.content import extract_text
from app.agentic.tools.packs.web.url_security import UnsafeUrlError, validate_url_syntax
from app.core.metrics import metrics
from app.infrastructure.browser_runtime import launch_full_chromium

logger = logging.getLogger(__name__)

BrowserMode = Literal["stealth", "dynamic"]
_MIN_CONTENT_LEN = 200
_CHALLENGE_TITLES = frozenset(
    {
        "verification",
        "access verification",
        "just a moment...",
        "安全验证",
        "访问验证",
        "人机验证",
    }
)
_CHALLENGE_TITLE_SUFFIXES = ("安全验证", "访问验证", "人机验证")
_CHALLENGE_MARKERS = (
    "attention required",
    "acw_sc__v2",
    "cf-chl-",
    "cf_app_waf",
    "checking your browser",
    "just a moment",
    "/cdn-cgi/challenge-platform",
    "verify you are human",
    "access verification",
    "slide to complete the verification process",
)
_CHALLENGE_INTERACTION_MARKERS = (
    "请完成下方验证",
    "拖动左侧滑块",
    "拖动滑块完成验证",
    "完成拼图验证",
    "正在验证，请稍候",
)
_STABILITY_POLL_SECONDS = 0.5
_BROWSER_QUEUE_TIMEOUT_SECONDS = 10.0
_MAX_BROWSER_REQUESTS = 256
_MAX_DOM_NODES = 100_000
_MAX_DOM_SAMPLE_NODES = 4_096
_MAX_DOM_SAMPLE_CHARS = 4_096
_MIN_BROWSER_TRANSFER_BYTES = 4 * 1024 * 1024
_BROWSER_TRANSFER_MULTIPLIER = 2
_SAFE_LOCAL_SCHEMES = frozenset({"about", "blob", "data"})
_BLOCKED_RESOURCE_TYPES = frozenset({"beacon", "font", "image", "media", "object", "texttrack"})
_BROWSER_FLAGS = [
    "--disable-dev-shm-usage",
    "--webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--force-webrtc-ip-handling-policy",
]
_BROWSER_CONTEXT = {
    "service_workers": "block",
    "ignore_https_errors": False,
    "accept_downloads": False,
    "permissions": [],
}


def normalize_scrapling_logging() -> None:
    """Route Scrapling logs through the application root handler exactly once."""
    names = [
        "scrapling",
        *(
            name
            for name in logging.Logger.manager.loggerDict
            if isinstance(name, str) and name.startswith("scrapling.")
        ),
    ]
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
    source_truncated: bool = False


class BrowserConcurrencyGate:
    """Process-local dynamic concurrency gate for browser launches."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active = 0

    @asynccontextmanager
    async def slot(self, limit: int, *, timeout_seconds: float) -> AsyncIterator[float]:
        queued_at = time.perf_counter()
        async with self._condition:
            try:
                async with asyncio.timeout(timeout_seconds):
                    await self._condition.wait_for(lambda: self._active < max(1, limit))
            except TimeoutError as error:
                raise BrowserResourceLimitError(f"浏览器并发队列等待超过 {timeout_seconds:g} 秒") from error
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


class BrowserRequestGuard:
    """Apply one fail-closed request policy to every page in a browser context."""

    def __init__(self, proxy: SafeBrowserProxy) -> None:
        self._proxy = proxy
        self._request_count = 0
        self._primary_page: Any | None = None
        self._page_close_tasks: set[asyncio.Task[None]] = set()
        self.fatal_error: Exception | None = None
        self.blocked_subresources = 0
        self.blocked_pages = 0

    @staticmethod
    def _is_navigation(request: Any) -> bool:
        check = getattr(request, "is_navigation_request", None)
        return bool(check()) if callable(check) else getattr(request, "resource_type", "") == "document"

    async def route(self, route: Any, request: Any) -> None:
        request_url = str(request.url)
        scheme = urlsplit(request_url).scheme.lower()
        is_navigation = self._is_navigation(request)

        self._request_count += 1
        if self._request_count > _MAX_BROWSER_REQUESTS:
            error = BrowserResourceLimitError(f"浏览器请求数量超过上限 {_MAX_BROWSER_REQUESTS}")
            self.fatal_error = error
            await route.abort("blockedbyclient")
            return

        resource_type = str(getattr(request, "resource_type", ""))
        if not is_navigation and resource_type in _BLOCKED_RESOURCE_TYPES:
            self.blocked_subresources += 1
            await route.abort("blockedbyclient")
            return

        if scheme in _SAFE_LOCAL_SCHEMES and not is_navigation:
            await route.continue_()
            return
        if scheme not in {"http", "https"}:
            error = UnsafeUrlError(f"浏览器请求拒绝 scheme={scheme!r}")
            if is_navigation:
                self.fatal_error = error
            else:
                self.blocked_subresources += 1
            await route.abort("blockedbyclient")
            return

        try:
            # The proxy reuses this exact cached DNS result when opening its socket.
            await self._proxy.resolve(request_url)
        except UnsafeUrlError as error:
            if is_navigation:
                self.fatal_error = error
            else:
                self.blocked_subresources += 1
                logger.info("已阻断非公网浏览器子资源: %s", request_url)
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    async def websocket(self, websocket: Any) -> None:
        self.blocked_subresources += 1
        await websocket.close(code=1008, reason="WebSocket disabled for safe browser fetch")

    async def _close_extra_page(self, page: Any) -> None:
        try:
            await page.close()
        except Exception as error:
            self.fatal_error = BrowserResourceLimitError("无法关闭额外浏览器页面")
            self.fatal_error.__cause__ = error

    def _handle_page(self, page: Any) -> None:
        if self._primary_page is None:
            self._primary_page = page
            return
        if page is self._primary_page:
            return
        self.blocked_pages += 1
        task = asyncio.create_task(self._close_extra_page(page))
        self._page_close_tasks.add(task)
        task.add_done_callback(self._page_close_tasks.discard)

    def set_primary_page(self, page: Any) -> None:
        if self._primary_page is not None and self._primary_page is not page:
            raise BrowserResourceLimitError("浏览器主页面数量超过上限 1")
        self._primary_page = page

    async def install(self, context: Any, *, primary_page: Any | None = None) -> None:
        if primary_page is not None:
            self.set_primary_page(primary_page)
        await context.route("**/*", self.route)
        await context.route_web_socket("**/*", self.websocket)
        context.on("page", self._handle_page)

    def raise_if_failed(self) -> None:
        if self.fatal_error is not None:
            raise self.fatal_error
        if self._proxy.limit_error is not None:
            raise self._proxy.limit_error


def _browser_transfer_limit(max_content_bytes: int) -> int:
    return max(_MIN_BROWSER_TRANSFER_BYTES, max_content_bytes * _BROWSER_TRANSFER_MULTIPLIER)


async def _bounded_dom_text(
    page: Any,
    *,
    max_chars: int,
    max_nodes: int,
) -> str:
    """Read a bounded text sample without serializing the complete DOM."""
    text = await page.evaluate(
        r"""({maxChars, maxNodes}) => {
            const root = document.body || document.documentElement;
            if (!root) return '';
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
            const chunks = [];
            let length = 0;
            let visited = 0;
            while (walker.nextNode() && length < maxChars && visited < maxNodes) {
                visited += 1;
                const remaining = maxChars - length;
                const raw = walker.currentNode.nodeValue || '';
                const value = raw.slice(0, remaining).replace(/\s+/g, ' ').trim();
                if (!value) continue;
                chunks.push(value.slice(0, remaining));
                length += Math.min(value.length, remaining) + 1;
            }
            return chunks.join(' ');
        }""",
        {"maxChars": max(1, max_chars), "maxNodes": max(1, max_nodes)},
    )
    return str(text or "")


async def _wait_for_stable_body(page: Any, settle_seconds: float) -> None:
    if settle_seconds <= 0:
        return
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settle_seconds
    previous_text: str | None = None
    while True:
        try:
            body_text = (
                await _bounded_dom_text(
                    page,
                    max_chars=_MAX_DOM_SAMPLE_CHARS,
                    max_nodes=_MAX_DOM_SAMPLE_NODES,
                )
            ).strip()
        except Exception:
            body_text = ""
        if len(body_text) >= _MIN_CONTENT_LEN and body_text == previous_text:
            return
        previous_text = body_text
        remaining = deadline - loop.time()
        if remaining <= 0:
            return
        await page.wait_for_timeout(int(min(_STABILITY_POLL_SECONDS, remaining) * 1000))


def _bounded_synthetic_html(title: str, text: str, max_content_bytes: int) -> str:
    """Build valid synthetic HTML whose UTF-8 representation stays within the limit."""
    prefix = "<html><head><title>"
    middle = "</title></head><body><p>"
    suffix = "</p></body></html>"
    fixed_bytes = len((prefix + middle + suffix).encode("utf-8"))
    if max_content_bytes < fixed_bytes:
        raise BrowserResourceLimitError("浏览器正文上限过小，无法生成安全 HTML")

    available = max_content_bytes - fixed_bytes
    # html.escape(..., quote=False) expands one source byte by at most five
    # bytes ("&" -> "&amp;"). Keep allocations and final output bounded.
    title_budget = min(512, available // 10)
    bounded_title, _ = _bounded_text(title, title_budget)
    escaped_title = html_lib.escape(bounded_title, quote=False)
    available -= len(escaped_title.encode("utf-8"))

    bounded_body, _ = _bounded_text(text, max(0, available // 5))
    escaped_body = html_lib.escape(bounded_body, quote=False)
    return prefix + escaped_title + middle + escaped_body + suffix


async def _capture_bounded_document(page: Any, max_content_bytes: int) -> tuple[str, bool]:
    """Serialize a bounded DOM, or replace it with bounded visible text."""
    if not hasattr(page, "evaluate"):
        raise BrowserResourceLimitError("浏览器页面不支持有界 DOM 提取")

    stats = await page.evaluate(
        r"""({maxNodes, maxBytes}) => {
            const root = document.documentElement;
            if (!root) return {nodes: 0, estimatedBytes: 0, exceeded: false};
            const walker = document.createTreeWalker(document, NodeFilter.SHOW_ALL);
            let nodes = 0;
            let estimatedBytes = 32;
            while (walker.nextNode()) {
                nodes += 1;
                if (nodes > maxNodes) {
                    return {nodes, estimatedBytes, exceeded: true};
                }
                const node = walker.currentNode;
                if (node.nodeType === Node.ELEMENT_NODE) {
                    estimatedBytes += 5 + (node.tagName || '').length * 12;
                    for (const attr of node.attributes || []) {
                        estimatedBytes += 4 + (attr.name.length + attr.value.length) * 6;
                    }
                } else if (node.nodeType === Node.DOCUMENT_TYPE_NODE) {
                    estimatedBytes += 16 + (
                        (node.name || '').length +
                        (node.publicId || '').length +
                        (node.systemId || '').length
                    ) * 6;
                } else {
                    estimatedBytes += 8 + (node.nodeValue || '').length * 6;
                }
                if (estimatedBytes > maxBytes) {
                    return {nodes, estimatedBytes, exceeded: true};
                }
            }
            return {nodes, estimatedBytes, exceeded: false};
        }""",
        {"maxNodes": _MAX_DOM_NODES, "maxBytes": max_content_bytes},
    )
    oversized = bool((stats or {}).get("exceeded", True))
    if not oversized:
        html = str(await page.content())
        if len(html.encode("utf-8")) <= max_content_bytes:
            return html, False

    text = await _bounded_dom_text(
        page,
        max_chars=max(1, max_content_bytes // 3),
        max_nodes=_MAX_DOM_NODES,
    )
    title = str(await page.title())
    return _bounded_synthetic_html(title, text, max_content_bytes), True


async def fetch_dynamic_document(
    url: str,
    *,
    navigation_timeout_seconds: float,
    settle_seconds: float,
    max_content_bytes: int,
    playwright_factory: Callable[[], Any] | None = None,
) -> RenderedDocument:
    """Render a dynamic page through the DNS-pinning loopback proxy."""
    if playwright_factory is None:
        from playwright.async_api import async_playwright

        playwright_factory = async_playwright

    limits = BrowserProxyLimits(max_response_bytes=_browser_transfer_limit(max_content_bytes))
    async with SafeBrowserProxy(limits=limits) as proxy:
        manager = playwright_factory()
        browser = None
        context = None
        async with manager as playwright:
            browser = await launch_full_chromium(
                playwright.chromium,
                args=[*_BROWSER_FLAGS, "--proxy-bypass-list=<-loopback>"],
                proxy={"server": proxy.url, "bypass": ""},
            )
            try:
                context = await browser.new_context(**_BROWSER_CONTEXT)
                try:
                    guard = BrowserRequestGuard(proxy)
                    await guard.install(context)
                    page = await context.new_page()
                    guard.set_primary_page(page)
                    try:
                        await page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=int(navigation_timeout_seconds * 1000),
                            referer="https://www.google.com/",
                        )
                    except Exception:
                        guard.raise_if_failed()
                        raise
                    guard.raise_if_failed()
                    final_url = str(page.url)
                    await proxy.resolve(final_url)
                    await _wait_for_stable_body(page, settle_seconds)
                    guard.raise_if_failed()
                    html, source_truncated = await _capture_bounded_document(page, max_content_bytes)
                    guard.raise_if_failed()
                    return RenderedDocument(
                        url=final_url,
                        title=await page.title(),
                        html=html,
                        source_truncated=source_truncated,
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
    source_truncated: bool = False,
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
    if is_challenge_page(title=result["title"], content=content, html=html):
        result["error"] = f"{mode} 浏览器返回了访问验证页"
    elif needs_fallback(content):
        result["error"] = f"{mode} 浏览器未提取到足够正文（{len(content)} 字符）"
    if truncated or source_truncated:
        result["note"] = f"浏览器页面及正文已限制为 {max_content_bytes} 字节"
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
                max_content_bytes=max_content_bytes,
            )
            return _browser_result(
                url=document.url,
                mode=mode,
                title=document.title,
                html=document.html,
                max_content_bytes=max_content_bytes,
                source_truncated=document.source_truncated,
            )

        fetcher = (fetchers or _load_fetchers())[mode]
        normalize_scrapling_logging()
        limits = BrowserProxyLimits(max_response_bytes=_browser_transfer_limit(max_content_bytes))
        async with SafeBrowserProxy(limits=limits) as proxy:
            guard = BrowserRequestGuard(proxy)
            guard_installed = False
            setup_error: Exception | None = None
            page_action_error: Exception | None = None
            source_truncated = False

            async def setup_request_guard(page: Any) -> None:
                nonlocal guard_installed, setup_error
                try:
                    await guard.install(page.context, primary_page=page)
                    guard_installed = True
                except Exception as error:
                    setup_error = error
                    with suppress(Exception):
                        await page.close()
                    raise

            async def limit_page_dom(page: Any) -> None:
                nonlocal page_action_error, source_truncated
                try:
                    await _wait_for_stable_body(page, settle_seconds)
                    bounded_html, source_truncated = await _capture_bounded_document(page, max_content_bytes)
                    if source_truncated:
                        await page.set_content(bounded_html, wait_until="domcontentloaded")
                except Exception as error:
                    page_action_error = error
                    with suppress(Exception):
                        await page.close()
                    raise

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
                "extra_flags": [*_BROWSER_FLAGS, "--proxy-bypass-list=<-loopback>"],
                "additional_args": dict(_BROWSER_CONTEXT),
                "proxy": proxy.url,
                "page_setup": setup_request_guard,
                "page_action": limit_page_dom,
            }
            if mode == "stealth":
                kwargs.update(block_webrtc=True, hide_canvas=True)
            try:
                page = await fetcher.async_fetch(url, **kwargs)
            except Exception:
                if setup_error is not None:
                    raise UnsafeUrlError("浏览器请求安全拦截器安装失败") from setup_error
                if page_action_error is not None:
                    raise BrowserResourceLimitError("浏览器 DOM 限制执行失败") from page_action_error
                guard.raise_if_failed()
                raise
            if setup_error is not None or not guard_installed:
                raise UnsafeUrlError("浏览器请求安全拦截器安装失败") from setup_error
            if page_action_error is not None:
                raise BrowserResourceLimitError("浏览器 DOM 限制执行失败") from page_action_error
            guard.raise_if_failed()

            final_url = str(getattr(page, "url", "") or url)
            await proxy.resolve(final_url)
            html = str(getattr(page, "html_content", "") or "")
            if html:
                return _browser_result(
                    url=final_url,
                    mode=mode,
                    title="",
                    html=html,
                    max_content_bytes=max_content_bytes,
                    source_truncated=source_truncated,
                )

            text = _clean_text(page.get_all_text(" ", ignore_tags=("script", "style", "noscript")))
            text, truncated = _bounded_text(text, max_content_bytes)
            title = ""
            if hasattr(page, "css"):
                title_elements = page.css("title")
                if title_elements:
                    title = (title_elements[0].text or "").strip()
            result = {
                "url": final_url,
                "title": title,
                "content": text,
                "content_type": "html",
                "content_length": len(text),
                "browser_mode": mode,
            }
            if is_challenge_page(title=title, content=text):
                result["error"] = f"{mode} 浏览器返回了访问验证页"
            elif needs_fallback(text):
                result["error"] = f"{mode} 浏览器未提取到足够正文（{len(text)} 字符）"
            if truncated or source_truncated:
                result["note"] = f"浏览器页面及正文已限制为 {max_content_bytes} 字节"
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
    queue_wait_ms = 0.0
    try:
        queue_timeout_seconds = min(_BROWSER_QUEUE_TIMEOUT_SECONDS, timeout_seconds)
        async with browser_gate.slot(
            settings.web_fetch_browser_max_concurrency,
            timeout_seconds=queue_timeout_seconds,
        ) as queue_wait_ms:
            remaining_timeout_seconds = max(0.001, timeout_seconds - queue_wait_ms / 1000)
            result = await _execute_browser_mode(
                url,
                mode,
                fetchers=fetchers,
                timeout_seconds=remaining_timeout_seconds,
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


def is_challenge_page(*, title: str = "", content: str = "", html: str = "") -> bool:
    """Return whether a response is an anti-bot or access-verification interstitial."""
    normalized_title = title.strip().lower()
    if normalized_title in _CHALLENGE_TITLES or normalized_title.endswith(_CHALLENGE_TITLE_SUFFIXES):
        return True

    sample = "\n".join((normalized_title, content[:4096], html[:8192])).lower()
    if any(marker in sample for marker in _CHALLENGE_MARKERS):
        return True

    # Chinese verification pages vary by provider, so use a combination of
    # interaction instructions instead of matching broad terms such as
    # "安全验证" or "验证码" in otherwise legitimate article content.
    interaction_hits = sum(marker in sample for marker in _CHALLENGE_INTERACTION_MARKERS)
    return interaction_hits >= 2


def needs_fallback(content: str) -> bool:
    return len(content) < _MIN_CONTENT_LEN


def _clean_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()
