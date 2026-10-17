"""个股研究图表的 PNG 渲染，供飞书卡片等外部消息渠道使用。"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

from app.core.market import market_today
from app.domain.market import KlineData
from app.financial_data.stock.quotes.kline import get_kline
from app.infrastructure.report import render_elements_to_pngs
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.pdf_service import (
    _render_price_chart,
    _render_valuation_chart,
    _render_volume_chart,
)

logger = logging.getLogger(__name__)

_CARD_WIDTH_PX = 780
_KLINE_TIMEOUT_SECONDS = 25.0


def _market_end_date(analysis_date: str) -> date:
    """将报告日期转换为行情截止日，避免历史报告引用未来数据。"""
    text = (analysis_date or "").strip()
    for date_format in ("%Y-%m-%d", "%Y%m%d"):
        try:
            parsed = datetime.strptime(text, date_format).date()
            return min(parsed, market_today())
        except (TypeError, ValueError):
            continue
    return market_today()


async def load_analysis_kline(stock_code: str, analysis_date: str) -> KlineData | None:
    """在事件循环上加载推送图表所需日 K（与个股 PDF 相同口径）；失败返回 None。

    必须在主事件循环调用：内部复用共享 singleflight，其锁绑定首个使用的循环。
    """
    end_date = _market_end_date(analysis_date)
    start_date = end_date - timedelta(days=400)
    try:
        return await asyncio.wait_for(
            get_kline(
                stock_code,
                period="daily",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                adjust="qfq",
                require_turnover=True,
            ),
            timeout=_KLINE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning(
            "推送图表行情加载超时 code=%s timeout_seconds=%.1f，略去行情图表",
            stock_code, _KLINE_TIMEOUT_SECONDS,
        )
        return None
    except Exception as error:
        logger.warning("推送图表行情加载失败 code=%s error_type=%s: %s", stock_code, type(error).__name__, error)
        return None


def analysis_chart_cards(
    result: AnalysisResult,
    kline_data: KlineData | None = None,
) -> list[tuple[str, str]]:
    """返回 (标题, 图表卡片 HTML) 列表；数据不足的图表自动略去。"""
    cards = (
        ("价格趋势与关键点位", _render_price_chart(result, kline_data)),
        ("量价配合", _render_volume_chart(kline_data)),
        ("估值与关键价位", _render_valuation_chart(result)),
    )
    return [(title, html) for title, html in cards if html]


def _card_page_html(card_html: str) -> str:
    # 与个股 PDF 的 .visual-card 样式保持一致，字号略放大以适配消息卡片
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<style>"
        "body{margin:0;background:#ffffff;}"
        f".visual-card{{background:#ffffff;border:1px solid #dbe4ee;border-radius:8px;"
        f"padding:14px 16px;width:{_CARD_WIDTH_PX}px;box-sizing:border-box;}}"
        ".visual-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:8px;}"
        ".visual-heading strong{color:#0f172a;font-size:15px;}"
        ".visual-heading span{color:#64748b;font-size:12px;text-align:right;}"
        ".visual-card svg{display:block;width:100%;height:auto;}"
        ".signal-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;}"
        ".signal-pill{font-size:11px;padding:2px 8px;border-radius:4px;}"
        "</style></head><body>"
        f'{card_html}</body></html>'
    )


def render_analysis_chart_pngs(
    result: AnalysisResult,
    kline_data: KlineData | None = None,
) -> list[tuple[str, bytes]]:
    """将个股研究图表卡片渲染为 PNG 字节，返回 (标题, PNG 字节) 列表。

    同步实现：推送链路在线程池中执行，不能使用 async playwright。
    渲染失败向上抛出，由调用方决定是否降级为纯文本推送。
    """
    cards = analysis_chart_cards(result, kline_data)
    if not cards:
        return []
    return render_elements_to_pngs(
        ((title, _card_page_html(card_html), ".visual-card") for title, card_html in cards),
        viewport_width=_CARD_WIDTH_PX + 40,
        viewport_height=600,
        missing_element_message="个股图表卡片渲染结果为空",
    )
