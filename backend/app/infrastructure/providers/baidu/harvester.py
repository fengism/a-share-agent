"""百度股市通 acs-token 与 Cookie 无头浏览器动态采集器。"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from app.constants.http import BROWSER_USER_AGENT
from app.core.timezones import SHANGHAI_TIMEZONE_NAME
from app.infrastructure.browser_runtime import launch_full_chromium

logger = logging.getLogger(__name__)

_DEFAULT_TARGET_URL = "https://gushitong.baidu.com/stock/ab-600519"
_DEFAULT_TTL_SECONDS = 3600.0  # 1 小时
_BROWSER_FLAGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
]


def _get_playwright_factory() -> Any:
    """优先使用内置的反爬专用 Patchright，降级使用原生 Playwright。"""
    try:
        from patchright.async_api import async_playwright as async_patchright

        return async_patchright
    except ImportError:
        pass
    try:
        from playwright.async_api import async_playwright

        return async_playwright
    except ImportError:
        return None


async def harvest_baidu_credentials(
    target_url: str = _DEFAULT_TARGET_URL,
    *,
    timeout_seconds: float = 15.0,
) -> tuple[str, str]:
    """启动无头 Chromium 访问百度股市通页面，动态捕获 acs-token 与 Cookie。

    Return:
        (cookie_str, acs_token) 元组；失败时返回 ("", "")。
    """
    factory = _get_playwright_factory()
    if factory is None:
        logger.warning("未检测到 Playwright/Patchright 运行时，跳过百度动态凭证采集")
        return "", ""

    captured_token: str | None = None
    captured_cookies: list[dict[str, Any]] = []

    try:
        async with factory() as playwright:
            browser = await launch_full_chromium(
                playwright.chromium,
                args=_BROWSER_FLAGS,
            )
            try:
                context = await browser.new_context(
                    user_agent=BROWSER_USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                    locale="zh-CN",
                    timezone_id=SHANGHAI_TIMEZONE_NAME,
                )

                def _on_request(request: Any) -> None:
                    nonlocal captured_token
                    headers = request.headers
                    for key, val in headers.items():
                        if key.lower() == "acs-token" and val and val.strip():
                            captured_token = val.strip()

                page = await context.new_page()
                page.on("request", _on_request)

                try:
                    await page.goto(
                        target_url,
                        wait_until="commit",
                        timeout=int(timeout_seconds * 1000),
                    )
                except Exception as exc:
                    logger.debug("百度凭证采集页面导航微小告警: %s", exc)

                # 页面网络提交后，等待异步行情接口触发并拦截其 acs-token
                for _ in range(25):
                    if captured_token:
                        break
                    await asyncio.sleep(0.2)

                captured_cookies = await context.cookies()
            finally:
                await browser.close()
    except Exception as exc:
        logger.warning("百度无头浏览器凭证采集失败: %s", exc)
        return "", ""

    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in captured_cookies)
    token_str = captured_token or ""
    logger.info(
        "百度无头浏览器凭证采集成功: has_token=%s, cookie_count=%d",
        bool(token_str),
        len(captured_cookies),
    )
    return cookie_str, token_str


class BaiduCredentialHarvester:
    """管理百度动态会话 Cookie 与 acs-token 的内存缓存与按需刷新。"""

    def __init__(self, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._cached_cookie: str = ""
        self._cached_token: str = ""
        self._cached_at: float = 0.0
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[tuple[str, str]] | None = None

    def is_valid(self) -> bool:
        with self._sync_lock:
            return bool(self._cached_token) and (time.monotonic() - self._cached_at < self._ttl_seconds)

    def get_credentials(self) -> tuple[str, str]:
        """同步读取当前有效凭证；无效时返回 ("", "")。"""
        with self._sync_lock:
            if self._cached_token and (time.monotonic() - self._cached_at < self._ttl_seconds):
                return self._cached_cookie, self._cached_token
        return "", ""

    def update(self, cookie: str, token: str) -> None:
        """更新缓存的凭证。"""
        with self._sync_lock:
            self._cached_cookie = cookie
            self._cached_token = token
            self._cached_at = time.monotonic()

    def invalidate(self) -> None:
        """使当前缓存的凭证失效（例如发生 403 风控时）。"""
        with self._sync_lock:
            self._cached_at = 0.0

    async def ensure_credentials(self, force: bool = False) -> tuple[str, str]:
        """异步确保凭证有效，过期或强制时启动无头浏览器刷新。"""
        if not force and self.is_valid():
            return self.get_credentials()

        async with self._async_lock:
            if not force and self.is_valid():
                return self.get_credentials()

            cookie, token = await harvest_baidu_credentials()
            if token:
                self.update(cookie, token)
            return self.get_credentials()

    def trigger_background_refresh(self) -> None:
        """在当前事件循环中非阻塞触发后台凭证刷新。"""
        if self.is_valid():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        with self._sync_lock:
            if self._refresh_task is not None and not self._refresh_task.done():
                return
            self._refresh_task = loop.create_task(self.ensure_credentials())


baidu_harvester = BaiduCredentialHarvester()
