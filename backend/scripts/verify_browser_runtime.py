"""Smoke-test all browser-backed backend capabilities.

Run this after installing only full Chromium, for example:

    patchright install --with-deps --no-shell chromium
    VERIFY_NO_HEADLESS_SHELL=1 python scripts/verify_browser_runtime.py
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path

from patchright.async_api import async_playwright as async_patchright
from playwright.async_api import async_playwright
from pypdf import PdfReader

from app.domain.market import KlineData, KlineItem
from app.infrastructure.browser_runtime import launch_full_chromium
from app.infrastructure.javascript_runtime import initialize_javascript_runtime
from app.modules.analysis.models import AnalysisResult, FactorAnalysis
from app.modules.analysis.pdf_service import generate_research_report_html, render_pdf_bytes_from_html
from app.modules.daily_review.models import DailyReviewDataSnapshot, DailyReviewResult, DailyReviewSection
from app.modules.daily_review.pdf_service import generate_daily_review_pdf_html, render_daily_review_pdf_bytes
from app.modules.industry_chain.models import (
    IndustryChainInsight,
    IndustryChainMetric,
    IndustryChainNode,
    IndustryChainResult,
)
from app.modules.industry_chain.pdf_service import generate_industry_chain_pdf_html, render_industry_chain_pdf_bytes

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


def _sample_report() -> AnalysisResult:
    factor = FactorAnalysis(score=5, summary="架构测试数据，不构成投资建议")
    return AnalysisResult(
        stock_code="600519",
        stock_name="PDF 架构自检",
        analysis_date="2026-09-28",
        current_price=100.0,
        fundamental=factor,
        technical=factor,
        sentiment=factor,
        overall_rating=5,
        overall_summary="原生 Chromium 个股报告导出测试",
        estimated_price_range=(90.0, 110.0),
        signal="hold",
        confidence=0.5,
    )


def _sample_daily_review() -> DailyReviewResult:
    section = DailyReviewSection(title="架构自检", summary="原生 Chromium 报告模板", bullets=["中文字体与分页"])
    return DailyReviewResult(
        date="2026-09-28",
        effective_date="2026-09-28",
        title="每日复盘 PDF 架构自检",
        generated_at="2026-09-28 18:00:00",
        market_state="balanced",
        position_range="四至六成",
        market_summary="验证 AMD64 与 ARM64 的真实每日复盘模板导出。",
        index_review=section,
        hotspot_review=section,
        dragon_tiger_review=section,
        opportunities=["架构兼容性验证"],
        risk_alerts=["测试内容不构成投资建议"],
        strategy_notes=["检查生成文件页数与 A4 尺寸"],
        data_snapshot=DailyReviewDataSnapshot(
            indices=[{"name": "上证指数", "price": 3200.0, "change_pct": 0.5}],
            market_volume={"amount": 1.6e12, "amount_before_one_day": 1.5e12},
        ),
    )


def _sample_industry_chain() -> IndustryChainResult:
    return IndustryChainResult(
        name="PDF 架构自检产业链",
        summary="验证 AMD64 与 ARM64 的真实产业链报告模板导出。",
        positioning="跨架构原生 Chromium PDF 回归检查",
        market_metrics=[IndustryChainMetric(label="测试市场规模", value="100 亿元", period="2026 年")],
        upstream=[IndustryChainNode(name="上游材料", companies=["示例公司 A"], role="原材料")],
        midstream=[IndustryChainNode(name="中游制造", companies=["示例公司 B"], role="制造")],
        downstream=[IndustryChainNode(name="下游应用", companies=["示例公司 C"], role="应用")],
        driver_insights=[IndustryChainInsight(title="架构驱动", detail="两个平台均应生成有效 A4 PDF")],
        risks=["测试内容不构成投资建议"],
    )


def _pdf_report_cases():
    analysis = _sample_report()
    daily_review = _sample_daily_review()
    industry_chain = _sample_industry_chain()
    return {
        "analysis": (render_pdf_bytes_from_html, generate_research_report_html(analysis), analysis.stock_name),
        "industry-chain": (
            render_industry_chain_pdf_bytes,
            generate_industry_chain_pdf_html(industry_chain),
            industry_chain.name,
        ),
        "daily-review": (
            render_daily_review_pdf_bytes,
            generate_daily_review_pdf_html(daily_review),
            daily_review.title,
        ),
    }


def _assert_valid_a4_pdf(name: str, pdf: bytes) -> None:
    if not pdf.startswith(b"%PDF-") or b"%%EOF" not in pdf[-1024:]:
        raise AssertionError(f"{name} renderer did not return a complete PDF")
    try:
        reader = PdfReader(BytesIO(pdf))
        pages = len(reader.pages)
    except Exception as exc:
        raise AssertionError(f"{name} renderer returned an unreadable PDF") from exc
    if pages < 1:
        raise AssertionError(f"{name} renderer returned a PDF with no pages")
    first_page = reader.pages[0]
    width = float(first_page.mediabox.width)
    height = float(first_page.mediabox.height)
    # Chromium reports A4 in PDF points (approximately 595 x 842); allow rounding differences.
    if not (590 <= width <= 600 and 837 <= height <= 847):
        raise AssertionError(f"{name} renderer returned non-A4 pages: {width}x{height}")
    print(f"{name} PDF smoke passed ({pages} pages, {len(pdf)} bytes, {width:.1f}x{height:.1f})")


async def _verify_pdf_renderers() -> None:
    for name, (renderer, content, marker) in _pdf_report_cases().items():
        if marker not in content:
            raise AssertionError(f"{name} smoke did not use its real report template")
        _assert_valid_a4_pdf(name, await renderer(content))


async def _verify_patchright() -> None:
    async with async_patchright() as patchright:
        browser = await launch_full_chromium(patchright.chromium, args=_FLAGS)
        try:
            page = await browser.new_page()
            await page.set_content(_HTML)
            assert await page.locator("#result").text_content() == "browser-ok"
        finally:
            await browser.close()


def _verify_node_drivers() -> None:
    # Use each SDK's resolver so PLAYWRIGHT_NODEJS_PATH overrides are tested too.
    # This internal API is pinned by uv.lock and is used only by the release smoke test.
    from patchright._impl._driver import compute_driver_executable as patchright_driver
    from playwright._impl._driver import compute_driver_executable as playwright_driver

    expected_arch = os.getenv("EXPECTED_ARCH") or platform.machine().lower()
    aliases = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}
    for sdk, resolve in (("playwright", playwright_driver), ("patchright", patchright_driver)):
        executable, _ = resolve()
        try:
            result = subprocess.run(
                [executable, "-p", "JSON.stringify({arch:process.arch,platform:process.platform})"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            actual = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise AssertionError(
                f"{sdk} Node driver failed before browser startup ({type(exc).__name__}); "
                "check image/host architecture and PLAYWRIGHT_NODEJS_PATH"
            ) from exc
        if actual.get("arch") != aliases.get(expected_arch, expected_arch) or actual.get("platform") != os.sys.platform:
            raise AssertionError(f"{sdk} Node driver architecture mismatch: expected={expected_arch}, actual={actual}")
        print(f"{sdk} Node driver: {actual['platform']}/{actual['arch']}")


def _verify_sync_chart_renderers() -> None:
    """Exercise the exact thread-pool sync Playwright path; never use push's error-swallowing wrappers."""
    from app.modules.analysis.chart_images import render_analysis_chart_pngs
    from app.modules.daily_review.chart_images import render_daily_review_chart_pngs
    from app.modules.daily_review.models import DailyReviewDataSnapshot
    from app.modules.industry_chain.chart_images import render_industry_chain_chart_pngs
    from app.modules.industry_chain.models import IndustryChainChart, IndustryChainResult

    report = _sample_report()
    kline = KlineData(
        code=report.stock_code,
        period="daily",
        adjust="qfq",
        items=[
            KlineItem(
                code=report.stock_code,
                date=f"2026-09-{day:02d}",
                open=100 + day,
                close=101 + day,
                high=102 + day,
                low=99 + day,
                volume=10000 * day,
                amount=1000000 * day,
            )
            for day in range(1, 21)
        ],
    )
    snapshot = DailyReviewDataSnapshot(
        indices=[{"name": "指数自检", "change_pct": 0.5}],
        market_volume={
            "amount": 1.6e12,
            "amount_before_one_day": 1.5e12,
            "amount_average_60_day": 1.7e12,
        },
    )
    chain = IndustryChainResult(
        name="图表自检",
        charts=[
            IndustryChainChart(
                title="环节对比",
                option={
                    "xAxis": {"type": "category", "data": ["上游", "下游"]},
                    "yAxis": {"type": "value"},
                    "series": [{"type": "bar", "data": [3, 5]}],
                },
            )
        ],
    )
    checks = (
        (
            "analysis",
            lambda: render_analysis_chart_pngs(report, kline),
            {"价格趋势与关键点位", "量价配合", "估值与关键价位"},
        ),
        ("daily-review", lambda: render_daily_review_chart_pngs(snapshot), {"核心指数表现", "市场成交额"}),
        ("industry-chain", lambda: render_industry_chain_chart_pngs(chain), {"环节对比"}),
    )
    for name, render, expected_titles in checks:
        images = render()
        if not expected_titles <= {title for title, _ in images}:
            raise AssertionError(f"{name} sync PNG renderer did not return all expected charts")
        if not all(png.startswith(b"\x89PNG\r\n\x1a\n") for _, png in images):
            raise AssertionError(f"{name} sync PNG renderer returned invalid image bytes")
        print(f"{name} sync PNG smoke test passed ({len(images)} charts)")


def _verify_native_runtime() -> None:
    aliases = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    machine = platform.machine().lower()
    actual = aliases.get(machine, machine)
    expected = os.getenv("EXPECTED_ARCH")
    if expected and actual != aliases.get(expected, expected):
        raise AssertionError(f"Expected native {expected} runtime, got {machine}")
    # These packages install overlapping files; installation order must never decide the V8 ABI.
    for legacy in ("py-mini-racer", "akracer"):
        try:
            version(legacy)
        except PackageNotFoundError:
            continue
        raise AssertionError(f"Conflicting legacy JavaScript runtime installed: {legacy}")
    initialize_javascript_runtime()
    from akshare.stock import stock_hk_sina
    from py_mini_racer import MiniRacer

    if stock_hk_sina.MiniRacer is not MiniRacer:
        raise AssertionError("AkShare is not using the shared MiniRacer implementation")
    with MiniRacer() as runtime:
        runtime.eval("function double(value) { return value * 2; }")
        if runtime.call("double", 21) != 42:
            raise AssertionError("MiniRacer call API smoke test failed")
    print(f"native runtime: {actual}, mini-racer={version('mini-racer')}")


async def _verify_isolated_chart_worker() -> None:
    from app.infrastructure.chart_runtime import render_chart_pngs

    result = await render_chart_pngs({"kind": "analysis", "data": _sample_report().model_dump(mode="json")})
    if not result or not all(png.startswith(b"\x89PNG\r\n\x1a\n") for _, png in result):
        raise AssertionError("Isolated PNG worker returned no valid images")
    print("isolated PNG worker smoke passed")


async def _verify_stealth_fetcher() -> None:
    # Local fixture only; exercise Scrapling's own lifecycle/options, not merely raw Patchright.
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    from scrapling.fetchers import StealthyFetcher

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = _HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = await StealthyFetcher.async_fetch(
            f"http://127.0.0.1:{server.server_port}/",
            headless=True,
            timeout=15000,
            network_idle=True,
            retries=1,
            dns_over_https=False,
            block_ads=False,
            block_webrtc=True,
            hide_canvas=True,
            extra_flags=_FLAGS,
        )
        if response.css("#result::text").get() != "browser-ok":
            raise AssertionError("Scrapling stealth JavaScript rendering failed")
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        thread.join(timeout=3)
    print("Scrapling stealth fetcher smoke passed")


async def main() -> None:
    await asyncio.to_thread(_verify_node_drivers)
    _verify_native_runtime()
    _assert_no_headless_shell()
    await _verify_dynamic_rendering()
    await _verify_pdf_renderers()
    await _verify_patchright()
    # Production push rendering is synchronous and runs off the HTTP event loop.
    await asyncio.to_thread(_verify_sync_chart_renderers)
    await _verify_isolated_chart_worker()
    await _verify_stealth_fetcher()
    print("browser runtime smoke test passed")


if __name__ == "__main__":
    asyncio.run(main())
