"""复盘图表的 PNG 渲染，供飞书卡片等外部消息渠道使用。"""

from __future__ import annotations

import logging

from playwright.sync_api import sync_playwright

from app.infrastructure.browser_runtime import full_chromium_launch_options
from app.modules.daily_review.models import DailyReviewDataSnapshot
from app.modules.daily_review.pdf_service import daily_review_chart_svgs

logger = logging.getLogger(__name__)

_SVG_WIDTH_PX = 560


def _chart_page_html(svg: str) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<style>body{margin:0;background:#ffffff;}"
        f"svg{{display:block;width:{_SVG_WIDTH_PX}px;height:auto;}}"
        "</style></head><body>"
        f"{svg}</body></html>"
    )


def render_daily_review_chart_pngs(snapshot: DailyReviewDataSnapshot) -> list[tuple[str, bytes]]:
    """将复盘 SVG 图表逐张渲染为 PNG 字节，返回 (标题, PNG 字节) 列表。

    同步实现：推送链路在线程池中执行，不能使用 async playwright。
    渲染失败向上抛出，由调用方决定是否降级为纯文本推送。
    """
    charts = daily_review_chart_svgs(snapshot)
    if not charts:
        return []
    images: list[tuple[str, bytes]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            **full_chromium_launch_options(args=["--no-sandbox", "--disable-setuid-sandbox"]),
        )
        try:
            page = browser.new_page(
                viewport={"width": _SVG_WIDTH_PX + 40, "height": 400},
                device_scale_factor=2,
            )
            for title, _subtitle, svg in charts:
                page.set_content(_chart_page_html(svg), wait_until="networkidle")
                element = page.query_selector("svg")
                if element is None:
                    logger.warning("图表 SVG 渲染结果为空，已跳过: title=%s", title)
                    continue
                images.append((title, element.screenshot()))
        finally:
            browser.close()
    return images
