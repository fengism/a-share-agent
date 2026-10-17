"""产业链 ECharts 图表的 PNG 渲染，供飞书卡片等外部消息渠道使用。

产业链图表以 ECharts option 形式随结果存储（前端渲染）；此处通过内置的
echarts.min.js 在本地 Chromium 中离线渲染并截图，不依赖任何外部网络资源。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.html import escape_html
from app.infrastructure.report import render_elements_to_pngs
from app.modules.industry_chain.models import IndustryChainResult

logger = logging.getLogger(__name__)

_ECHARTS_PATH = Path(__file__).parent / "assets" / "echarts.min.js"
_CONTAINER_WIDTH_PX = 1080
_CONTAINER_HEIGHT_PX = 560
_MAX_CHARTS = 3
_echarts_source: str | None = None


def _load_echarts_source() -> str:
    """读取内置 echarts.min.js（进程内缓存）；缺失时抛错由调用方降级。"""
    global _echarts_source
    if _echarts_source is None:
        if not _ECHARTS_PATH.exists():
            raise FileNotFoundError(f"echarts.min.js 未随应用分发: {_ECHARTS_PATH}")
        _echarts_source = _ECHARTS_PATH.read_text(encoding="utf-8")
    return _echarts_source


def _json_for_script(value: object) -> str:
    # 防止 option 文本中出现 </script> 提前闭合内联脚本
    return json.dumps(value, ensure_ascii=False, default=str).replace("</", "<\\/")


def industry_chain_chart_cards(
    result: IndustryChainResult,
    *,
    max_charts: int = _MAX_CHARTS,
) -> list[tuple[str, str, dict]]:
    """返回 (标题, 描述, ECharts option) 列表；无 option 的图表自动略去。"""
    cards: list[tuple[str, str, dict]] = []
    for chart in result.charts:
        if not chart.option:
            continue
        title = chart.title or "产业链图表"
        description = chart.description or ""
        cards.append((title, description, chart.option))
        if len(cards) >= max_charts:
            break
    return cards


def _chart_page_html(title: str, description: str, option: dict, echarts_source: str) -> str:
    heading = (
        f'<div class="chart-heading"><strong>{escape_html(title)}</strong>'
        + (f"<span>{escape_html(description)}</span>" if description else "")
        + "</div>"
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<style>"
        "body{margin:0;background:#ffffff;font-family:'PingFang SC','Microsoft YaHei',sans-serif;}"
        ".chart-panel{background:#ffffff;border:1px solid #dbe4ee;border-radius:8px;"
        f"padding:14px 16px;width:{_CONTAINER_WIDTH_PX + 32}px;box-sizing:border-box;}}"
        ".chart-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:8px;}"
        ".chart-heading strong{color:#0f172a;font-size:15px;}"
        ".chart-heading span{color:#64748b;font-size:12px;text-align:right;}"
        "</style></head><body>"
        f'<div class="chart-panel">{heading}'
        f'<div id="chart" style="width:{_CONTAINER_WIDTH_PX}px;height:{_CONTAINER_HEIGHT_PX}px;"></div>'
        "</div>"
        f"<script>{echarts_source}</script>"
        "<script>"
        "var chart = echarts.init(document.getElementById('chart'), null, {renderer: 'canvas'});"
        f"chart.setOption(Object.assign({{animation: false}}, {_json_for_script(option)}));"
        "</script>"
        "</body></html>"
    )


def render_industry_chain_chart_pngs(
    result: IndustryChainResult,
    *,
    max_charts: int = _MAX_CHARTS,
) -> list[tuple[str, bytes]]:
    """将产业链 ECharts 图表渲染为 PNG 字节，返回 (标题, PNG 字节) 列表。

    同步实现：推送链路在线程池中执行，不能使用 async playwright。
    渲染失败向上抛出，由调用方决定是否降级为纯文本推送。
    """
    cards = industry_chain_chart_cards(result, max_charts=max_charts)
    if not cards:
        return []
    echarts_source = _load_echarts_source()
    return render_elements_to_pngs(
        (
            (title, _chart_page_html(title, description, option, echarts_source), ".chart-panel")
            for title, description, option in cards
        ),
        viewport_width=_CONTAINER_WIDTH_PX + 72,
        viewport_height=_CONTAINER_HEIGHT_PX + 120,
        missing_element_message="产业链图表渲染结果为空",
        wait_until="load",
        # ECharts 需要等画布真的挂上去，否则截图可能拿到空白容器
        ready_selector="#chart canvas",
    )
