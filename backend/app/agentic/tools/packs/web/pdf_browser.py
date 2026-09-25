"""Bounded PDF retrieval after a site's JavaScript access verification."""

from __future__ import annotations

import asyncio
import base64
from typing import Any

from app.agentic.tools.packs.web.browser_proxy import BrowserProxyLimits, SafeBrowserProxy
from app.agentic.tools.packs.web.scrapling import (
    _BROWSER_CONTEXT,
    _BROWSER_FLAGS,
    BrowserRequestGuard,
    _browser_gate,
)
from app.agentic.tools.packs.web.url_security import validate_url_syntax
from app.infrastructure.browser_runtime import launch_full_chromium

# Read via the page's network stack (not APIRequestContext, which bypasses the
# request guard). Chromium's PDF viewer returns synthetic HTML from response.body().
_READ_PDF = """async ({url, maxBytes}) => {
    const response = await fetch(url, {credentials: 'same-origin'});
    if (!response.ok) throw new Error(`PDF HTTP ${response.status}`);
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    try {
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            size += value.length;
            if (size > maxBytes) throw new Error('PDF response exceeds byte limit');
            chunks.push(value);
        }
    } finally {
        await reader.cancel();
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    let binary = '';
    for (let i = 0; i < size; i += 32768) {
        binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
    }
    return btoa(binary);
}"""


def _is_pdf_navigation(response: Any) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return response.request.is_navigation_request() and (
        "application/pdf" in content_type or "application/octet-stream" in content_type
    )


async def fetch_pdf_in_browser(url: str) -> bytes:
    """Use the shared browser gate, SSRF guard and pinned, byte-limited proxy.

    Call only after detecting an access-verification response. Browser work,
    including queueing and any challenge reloads, has one overall deadline.
    """
    from playwright.async_api import async_playwright

    from app.configuration import get_settings

    settings = get_settings()
    if not settings.web_fetch_browser_enabled:
        raise RuntimeError("浏览器抓取未启用")
    validate_url_syntax(url)
    timeout = min(settings.web_fetch_browser_timeout_seconds, 30.0)
    max_bytes = settings.web_fetch_max_response_bytes
    # The browser may transfer the PDF for its viewer and then once for extraction.
    limits = BrowserProxyLimits(max_response_bytes=max_bytes * 2 + 1024 * 1024)
    async with asyncio.timeout(timeout), _browser_gate.slot(
        settings.web_fetch_browser_max_concurrency,
        timeout_seconds=min(10.0, timeout),
    ), SafeBrowserProxy(limits=limits) as proxy, async_playwright() as playwright:
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
                    async with page.expect_response(_is_pdf_navigation, timeout=timeout * 1000):
                        await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                    # A challenge-triggered reload may still be committing here.
                    await page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
                    guard.raise_if_failed()
                    final_url = str(page.url)
                    await proxy.resolve(final_url)
                    encoded = await page.evaluate(_READ_PDF, {"url": final_url, "maxBytes": max_bytes})
                    guard.raise_if_failed()
                    if len(encoded) > 4 * ((max_bytes + 2) // 3):
                        raise ValueError("PDF response exceeds byte limit")
                    content = base64.b64decode(encoded, validate=True)
                    if len(content) > max_bytes:
                        raise ValueError("PDF response exceeds byte limit")
                    return content
                except Exception:
                    guard.raise_if_failed()
                    raise
            finally:
                await context.close()
        finally:
            await browser.close()
