"""Smoke-test all browser-backed backend capabilities.

Run this after installing only full Chromium, for example:

    patchright install --with-deps --no-shell chromium
    VERIFY_NO_HEADLESS_SHELL=1 python scripts/verify_browser_runtime.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from patchright.async_api import async_playwright as async_patchright
from playwright.async_api import async_playwright

from app.infrastructure.browser_runtime import launch_full_chromium
from app.modules.analysis.pdf_service import render_pdf_bytes_from_html
from app.modules.daily_review.pdf_service import render_daily_review_pdf_bytes
from app.modules.industry_chain.pdf_service import render_industry_chain_pdf_bytes

_HTML = """<!doctype html>
<html><body><div id="result">waiting</div>
<script>document.querySelector('#result').textContent = 'browser-ok';</script>
</body></html>"""
_FLAGS = ["--no-sandbox", "--disable-setuid-sandbox"]


def _assert_no_headless_shell() -> None:
    if os.getenv("VERIFY_NO_HEADLESS_SHELL") != "1":
        return
    browser_path = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    shells = list(browser_path.glob("chromium_headless_shell-*"))
    if shells:
        raise AssertionError(f"Unexpected headless-shell artifacts: {shells}")


async def _verify_dynamic_rendering() -> None:
    async with async_playwright() as playwright:
        browser = await launch_full_chromium(playwright.chromium, args=_FLAGS)
        try:
            page = await browser.new_page()
            await page.set_content(_HTML)
            assert await page.locator("#result").text_content() == "browser-ok"
        finally:
            await browser.close()


async def _verify_pdf_renderers() -> None:
    renderers = {
        "analysis": render_pdf_bytes_from_html,
        "industry-chain": render_industry_chain_pdf_bytes,
        "daily-review": render_daily_review_pdf_bytes,
    }
    for name, renderer in renderers.items():
        pdf = await renderer(_HTML)
        if not pdf.startswith(b"%PDF-"):
            raise AssertionError(f"{name} renderer did not return a PDF")


async def _verify_patchright() -> None:
    async with async_patchright() as patchright:
        browser = await launch_full_chromium(patchright.chromium, args=_FLAGS)
        try:
            page = await browser.new_page()
            await page.set_content(_HTML)
            assert await page.locator("#result").text_content() == "browser-ok"
        finally:
            await browser.close()


async def main() -> None:
    _assert_no_headless_shell()
    await _verify_dynamic_rendering()
    await _verify_pdf_renderers()
    await _verify_patchright()
    print("browser runtime smoke test passed")


if __name__ == "__main__":
    asyncio.run(main())
