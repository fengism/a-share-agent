"""报表图表的同步 PNG 渲染（PDF 与外部推送共用）。

个股分析、产业链、每日复盘三个模块都要把内联 HTML（含 SVG 或 ECharts）截图成
PNG，交给飞书等消息渠道。浏览器启动参数、视口、设备倍率、元素缺失降级与异常
清理此前在三个文件里逐行重复，这里收敛为一处，保证启动策略不再漂移。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Literal

from playwright.sync_api import sync_playwright

from app.infrastructure.browser_runtime import full_chromium_launch_options

logger = logging.getLogger(__name__)

#: 2x 截图，保证消息卡片在高分屏上不糊
DEFAULT_DEVICE_SCALE_FACTOR = 2

#: 与 PDF 渲染保持一致：容器内以非 root 运行时需要显式关闭沙箱
_SANDBOX_ARGS = ("--no-sandbox", "--disable-setuid-sandbox")

#: Playwright 的页面就绪策略：ECharts 需要在脚本执行完后才能截图
WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]

#: ECharts 画布渲染完成的等待上限
DEFAULT_READY_TIMEOUT_MS = 10_000


def render_elements_to_pngs(
    jobs: Iterable[tuple[str, str, str]],
    *,
    viewport_width: int,
    viewport_height: int,
    device_scale_factor: int = DEFAULT_DEVICE_SCALE_FACTOR,
    missing_element_message: str = "图表元素渲染结果为空",
    wait_until: WaitUntil = "networkidle",
    ready_selector: str | None = None,
    ready_timeout_ms: int = DEFAULT_READY_TIMEOUT_MS,
) -> list[tuple[str, bytes]]:
    """把 ``(标题, 页面 HTML, 元素选择器)`` 逐条渲染为 ``(标题, PNG 字节)``。

    同步实现：推送链路在线程池中执行，不能使用 async playwright。
    渲染失败向上抛出，由调用方决定是否降级为纯文本推送。

    Param:
        jobs: 渲染任务；选择器命不中时跳过该条并留日志
        viewport_width / viewport_height: 页面视口尺寸（像素）
        device_scale_factor: 截图倍率
        missing_element_message: 选择器命不中时的日志前缀
        wait_until: ``set_content`` 的就绪策略
        ready_selector: 非空时先等待该元素出现（ECharts 画布等）
        ready_timeout_ms: ``ready_selector`` 的等待上限
    Return:
        成功渲染的 ``(标题, PNG 字节)`` 列表；无任务或全部跳过后为空列表
    """
    pending = [(title, html, selector) for title, html, selector in jobs if selector]
    if not pending:
        return []

    images: list[tuple[str, bytes]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            **full_chromium_launch_options(args=list(_SANDBOX_ARGS)),
        )
        try:
            page = browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=device_scale_factor,
            )
            for title, html, selector in pending:
                page.set_content(html, wait_until=wait_until)
                if ready_selector is not None:
                    page.wait_for_selector(ready_selector, timeout=ready_timeout_ms)
                element = page.query_selector(selector)
                if element is None:
                    logger.warning("%s，已跳过: title=%s", missing_element_message, title)
                    continue
                images.append((title, element.screenshot()))
        finally:
            browser.close()
    return images
