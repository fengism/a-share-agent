"""Bounded shared PDF/PNG permits; PDF rendering for HTTP report exports.

Limits are per process/event loop; production runs one Uvicorn worker. Queue wait
and browser work share one deadline. Cleanup is bounded separately and completes
before releasing the render permit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from playwright.async_api import async_playwright

from app.configuration import get_settings
from app.core.exceptions import UpstreamUnavailableError
from app.infrastructure.browser_runtime import launch_full_chromium
from app.infrastructure.cleanup import wait_for_cleanup
from app.infrastructure.render_queue import get_render_limiter as _limiter

logger = logging.getLogger(__name__)
_CLEANUP_SECONDS = 5.0
_deferred_cleanups: set[asyncio.Task[None]] = set()


def _finish_deferred_cleanup(task: asyncio.Task[None]) -> None:
    _deferred_cleanups.discard(task)
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.warning("PDF deferred cleanup failed error_type=%s", type(error).__name__)


async def _cleanup(resource: Any, method: str) -> bool:
    try:
        await asyncio.wait_for(getattr(resource, method)(), timeout=_CLEANUP_SECONDS)
        return True
    except Exception as exc:
        logger.warning("PDF runtime cleanup failed operation=%s error_type=%s", method, type(exc).__name__)
        return False


async def _close_resources(
    browser: Any, driver: Any, manager: Any = None, startup: asyncio.Task[Any] | None = None,
) -> None:
    if driver is None and startup is not None:
        # Playwright starts its transport in an independent task. __aexit__ is
        # unsafe until start() has settled, even if the request was cancelled.
        try:
            driver = await startup
        except Exception:
            # The request keeps the startup error; still clean a failed manager.
            pass
    if browser is not None:
        await _cleanup(browser, "close")
    if driver is not None:
        if not await _cleanup(driver, "stop"):
            raise UpstreamUnavailableError("PDF 驱动未能退出，请重启后端", code="render.cleanup_failed")
    elif manager is not None:
        # start() can allocate a Node transport before it returns the driver.
        try:
            await asyncio.wait_for(manager.__aexit__(None, None, None), timeout=_CLEANUP_SECONDS)
        except Exception as exc:
            logger.warning("PDF initialization cleanup failed error_type=%s", type(exc).__name__)
            raise UpstreamUnavailableError("PDF 驱动初始化清理失败，请重启后端", code="render.cleanup_failed") from exc


async def _bounded_cleanup(browser: Any, driver: Any, manager: Any, startup: asyncio.Task[Any]) -> None:
    task = asyncio.create_task(_close_resources(browser, driver, manager, startup))
    try:
        # Allow initialization, browser close and driver stop their cleanup
        # budgets. Never cancel startup: a late driver must still be reaped.
        await asyncio.wait_for(asyncio.shield(task), timeout=3 * _CLEANUP_SECONDS)
    except TimeoutError as exc:
        _deferred_cleanups.add(task)
        task.add_done_callback(_finish_deferred_cleanup)
        raise UpstreamUnavailableError("PDF 驱动初始化清理超时，请重启后端", code="render.cleanup_failed") from exc


async def render_pdf(html_content: str, *, header_template: str, footer_template: str) -> bytes:
    settings = get_settings()
    limiter = _limiter()
    try:
        async with asyncio.timeout(settings.pdf_render_timeout_seconds), limiter.slot():
            driver = None
            browser = None
            manager = async_playwright()
            startup = asyncio.create_task(manager.start())
            try:
                driver = await asyncio.shield(startup)
                browser = await launch_full_chromium(driver.chromium, args=["--no-sandbox", "--disable-setuid-sandbox"])
                page = await browser.new_page()
                await page.set_content(html_content, wait_until="networkidle")
                result = await page.pdf(
                    format="A4",
                    print_background=True,
                    display_header_footer=True,
                    header_template=header_template,
                    footer_template=footer_template,
                    margin={"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
                )
                if not isinstance(result, bytes) or not result.startswith(b"%PDF-"):
                    raise UpstreamUnavailableError("PDF 渲染未返回有效文件", code="pdf.invalid_output")
                return result
            finally:
                try:
                    await wait_for_cleanup(asyncio.create_task(_bounded_cleanup(browser, driver, manager, startup)))
                except Exception:
                    limiter.quarantined = True
                    raise
    except TimeoutError as exc:
        raise UpstreamUnavailableError("PDF 导出等待或渲染超时，请稍后重试", code="pdf.timeout") from exc
