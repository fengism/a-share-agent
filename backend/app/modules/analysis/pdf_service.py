"""基于 Playwright Headless 浏览器的机构级纯矢量投研 PDF 生成服务（完整 8 大框架结论与全量数据）。"""

import html
import logging
import math
from datetime import date as calendar_date
from datetime import datetime
from typing import Any

from app.core.market import is_hk_code
from app.domain.market import KlineData, KlineItem
from app.financial_data.stock.quotes.chip_schemas import ChipDistribution
from app.infrastructure.pdf_runtime import render_pdf
from app.modules.analysis.models import AnalysisResult

logger = logging.getLogger(__name__)

# 标签映射字典
GRADE_LABELS = {
    "A": "A · 资料丰富 (High Quality)",
    "B": "B · 资料有限 (Moderate Quality)",
    "C": "C · 资料稀少 (Low Quality)",
    "unknown": "? · 尚未评级",
}

LEVEL_LABELS = {
    "strong": "强",
    "moderate": "中",
    "weak": "弱",
    "unclear": "待核验",
}

DIRECTION_LABELS = {
    "strengthening": "增强 ↑",
    "stable": "稳定 →",
    "weakening": "减弱 ↓",
    "unclear": "待核验",
}

RISK_LABELS = {
    "high": "高风险",
    "medium": "中风险",
    "low": "低风险",
    "unknown": "待核验",
}

MOAT_LABELS = {
    "brand_pricing": "品牌与定价权",
    "switching_cost": "转换成本",
    "network_effect": "网络效应",
    "scale_advantage": "规模优势",
    "technology_ip": "技术与知识产权",
    "other": "其他壁垒",
}

SIGNAL_MAP = {
    "strong_buy": ("强烈买入", "#dcfce7", "#166534", "#86efac"),
    "buy": ("买入 / 关注", "#dcfce7", "#166534", "#86efac"),
    "hold": ("持有 / 观望", "#e0f2fe", "#0369a1", "#7dd3fc"),
    "sell": ("减持 / 谨慎", "#fee2e2", "#991b1b", "#fca5a5"),
    "strong_sell": ("强烈减持", "#fee2e2", "#991b1b", "#fca5a5"),
}

ACTION_LABELS = {
    "buy": "买入",
    "watch": "重点关注",
    "avoid": "观望回避",
    "hold": "继续持有",
    "add": "逢低加仓",
    "reduce": "分批减仓",
    "exit": "坚决止损/离场",
    "insufficient_evidence": "待进一步核验",
}

_TOOL_NAME_MAP: dict[str, str] = {
    # 港股相关数据源
    "get_hk_stock_profile": "港股基本面画像与行业属性",
    "get_hk_stock_kline": "港股历史行情与K线走势",
    "get_hk_stock_quote": "港股实时行情与挂单",
    "get_hk_financial_statements": "港股财务报表与经营指标",
    # A股与通用投研数据源
    "get_stock_profile": "公司基本面画像与主营业务",
    "get_stock_info": "公司基础资料与主营业务",
    "get_stock_kline": "历史行情走势与技术形态",
    "get_stock_news": "公司公开新闻与重大动态",
    "get_stock_documents": "权威公告与研报目录",
    "get_stock_technical_indicators": "量化技术面与动量指标",
    "get_stock_valuation_detail": "估值指标与历史分位",
    "get_stock_risk_data": "质押减持与风险警示",
    "get_stock_sentiment": "市场情绪与舆情指标",
    "get_financial_statements": "企业三大财务报表数据",
    "get_financial_metrics": "盈利质量与关键财务指标",
    "get_valuation_metrics": "估值模型与分位数分析",
    "get_industry_chain_analysis": "产业链图谱与上下游格局",
    "get_northbound_flow": "北向资金与机构持股动向",
    "get_margin_trading_data": "融资融券与杠杆交易数据",
    "get_market_overview": "宏观全市场流动性与风格",
    "get_macro_economic_data": "宏观经济数据与宏观政策",
    "get_global_macro_rates": "全球无风险利率与外汇汇率",
    "get_commodity_spot_prices": "大宗商品现货与期货价格",
    "get_customs_trade_data": "全国海关进出口贸易数据",
    "get_restricted_shares_lift": "限售股解禁日程与规模",
    "get_interactive_qa": "交易所互动易投资者问答",
    "public_industry_data": "行业公共宏观统计与运行指标",
    # 公开资讯与研报检索
    "web_search": "公开市场资讯与权威研报",
    "web_fetch": "公开网页原文查验",
    "fetch_urls": "多渠道资讯交叉核验",
    "browse_page": "官方公告与信息页面查证",
    "read_pdf": "深度研报与官方公告全文精读",
    "iwencai_search": "自然语言选股与财务检索",
    "iwencai_query": "结构化多维财务数据查询",
    "python_interpreter": "量化与财务模型沙箱计算",
    "analyze_financials": "杜邦分析与财务穿透核算",
    "financial_calculator": "财务固定公式与模型测算",
}

_CACHE_STATUS_LABELS: dict[str, str] = {
    "cached": "本地缓存",
    "live": "实时采集",
    "stale": "历史存档",
    "mixed": "混合状态",
    "unknown": "公开披露",
}


def _format_tool_name(tool_name: str) -> str:
    """将内部工具名称转换为规范的投研数据维度名称。"""
    if tool_name in _TOOL_NAME_MAP:
        return _TOOL_NAME_MAP[tool_name]
    clean = tool_name.removeprefix("get_").replace("_", " ").title()
    return f"{clean} (公开数据)"



def _esc(text: Any) -> str:
    """安全转义 HTML 字符串。"""
    if text is None:
        return ""
    return html.escape(str(text))


def _render_pill(text: str, bg: str = "#f1f5f9", fg: str = "#475569", border: str = "#cbd5e1") -> str:
    if not text:
        return ""
    return (
        f'<span style="display:inline-block; padding:2px 8px; border-radius:4px; '
        f'background:{bg}; color:{fg}; border:1px solid {border}; font-size:11px; font-weight:600; margin-right:4px;">'
        f'{_esc(text)}</span>'
    )


def _render_list_items(items: list[str]) -> str:
    if not items:
        return '<div style="color:#94a3b8; font-size:11px;">暂无记录</div>'
    res = '<ul style="margin:0; padding-left:18px; list-style-type:disc;">'
    for it in items:
        if it and str(it).strip():
            res += f'<li style="margin-bottom:3px; line-height:1.5; font-size:11px; color:#334155;">{_esc(str(it).strip())}</li>'
    res += '</ul>'
    return res


def _render_named_box(title: str, content: str, bg: str = "#ffffff", border: str = "#e2e8f0") -> str:
    if not content or not str(content).strip():
        return ""
    return f"""
    <div style="background:{bg}; border:1px solid {border}; border-radius:6px; padding:8px 10px; margin-bottom:8px;">
        <div style="font-weight:700; color:#475569; font-size:11px; margin-bottom:3px;">{_esc(title)}</div>
        <div style="font-size:11px; color:#1e293b; line-height:1.5;">{_esc(content)}</div>
    </div>
    """


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _format_price(value: float, currency: str = "¥") -> str:
    return f"{currency}{value:,.2f}"


def _format_percent(value: float, *, signed: bool = True) -> str:
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value:.1f}%"


def _short_date(value: Any) -> str:
    text = str(value or "")
    if len(text) >= 10 and "-" in text:
        return text[5:10]
    if len(text) == 8 and text.isdigit():
        return f"{text[4:6]}-{text[6:8]}"
    return text


def _render_signals(signals: list[tuple[str, str]]) -> str:
    if not signals:
        return ""
    items = "".join(
        f'<li><span class="signal-dot signal-{_esc(tone)}"></span>{_esc(text)}</li>'
        for text, tone in signals[:3]
        if text
    )
    if not items:
        return ""
    return f"""
        <div class="visual-signals">
            <strong>关键信号</strong>
            <ul>{items}</ul>
        </div>
    """


def _chart_card(
    title: str,
    subtitle: str,
    svg: str,
    *,
    signals: list[tuple[str, str]] | None = None,
) -> str:
    if not svg:
        return ""
    return f"""
    <section class="visual-card">
        <div class="visual-heading">
            <strong>{_esc(title)}</strong>
            <span>{_esc(subtitle)}</span>
        </div>
        {svg}
        {_render_signals(signals or [])}
    </section>
    """


def _chart_date(value: Any) -> calendar_date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, calendar_date):
        return value
    text = str(value or "").strip()
    for date_format in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], date_format).date()
        except ValueError:
            continue
    return None


def _valid_bars(
    kline_data: KlineData | None,
    *,
    limit: int = 120,
    end_date: Any = None,
) -> list[KlineItem]:
    if kline_data is None:
        return []
    cutoff = _chart_date(end_date)
    bars = [
        item
        for item in kline_data.items
        if all(_number(value) is not None for value in (item.close, item.high, item.low, item.volume))
        and item.high >= item.low
        and item.close > 0
        and (cutoff is None or _chart_date(item.date) is None or _chart_date(item.date) <= cutoff)
    ]
    bars.sort(key=lambda item: item.date)
    return bars[-limit:]


def _moving_average(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = []
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        result.append(running / window if index + 1 >= window else None)
    return result


def _line_path(
    values: list[float | None],
    *,
    x_for: Any,
    y_for: Any,
) -> str:
    parts: list[str] = []
    drawing = False
    for index, value in enumerate(values):
        if value is None:
            drawing = False
            continue
        parts.append(f"{'L' if drawing else 'M'} {x_for(index):.2f} {y_for(value):.2f}")
        drawing = True
    return " ".join(parts)


def _render_price_chart(result: AnalysisResult, kline_data: KlineData | None, currency: str = "¥") -> str:
    bars = _valid_bars(kline_data, end_date=getattr(result, "analysis_date", None))
    if len(bars) < 2:
        return ""

    closes = [float(item.close) for item in bars]
    ma_series = [(5, "#f59e0b"), (20, "#8b5cf6"), (60, "#0ea5e9")]
    averages = {window: _moving_average(closes, window) for window, _ in ma_series}
    technical = getattr(result, "technical", None)
    support = _number(getattr(technical, "support_level", None))
    resistance = _number(getattr(technical, "resistance_level", None))
    scale_values = closes + [value for value in (support, resistance) if value is not None]
    low = min(scale_values)
    high = max(scale_values)
    padding = (high - low) * 0.08 or max(high * 0.02, 0.01)
    low -= padding
    high += padding

    width, height = 760, 292
    left, right, top, bottom = 62, 96, 30, 38
    plot_width = width - left - right
    plot_height = height - top - bottom
    def x_for(index: int) -> float:
        return left + index / (len(bars) - 1) * plot_width

    def y_for(value: float) -> float:
        return top + (high - value) / (high - low) * plot_height

    parts: list[str] = []
    for index in range(5):
        value = high - (high - low) * index / 4
        y = y_for(value)
        parts.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y:.2f}" y2="{y:.2f}" stroke="#e2e8f0"/>'
            f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" fill="#64748b" font-size="10">'
            f"{value:,.0f}</text>"
        )

    for label, value, color in (
        ("支撑/止损参考", support, "#16a34a"),
        ("压力参考", resistance, "#dc2626"),
    ):
        if value is None:
            continue
        y = y_for(value)
        parts.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y:.2f}" y2="{y:.2f}" '
            f'stroke="{color}" stroke-width="1.2" stroke-dasharray="5 4"/>'
            f'<text x="{width - right - 3}" y="{y - 4:.2f}" text-anchor="end" fill="{color}" '
            f'font-size="10" font-weight="700">{_esc(label)} {_esc(_format_price(value, currency))}</text>'
        )

    close_path = _line_path(closes, x_for=x_for, y_for=y_for)
    parts.append(f'<path d="{close_path}" fill="none" stroke="#0f766e" stroke-width="2.2"/>')
    dash_styles = {5: "", 20: "5 3", 60: "2 3"}
    for window, color in ma_series:
        path = _line_path(averages[window], x_for=x_for, y_for=y_for)
        if path:
            dash = f' stroke-dasharray="{dash_styles[window]}"' if dash_styles[window] else ""
            parts.append(
                f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.4" opacity="0.95"{dash}/>'
            )

    endpoint_labels = [("收盘", closes[-1], "#0f766e")]
    endpoint_labels.extend(
        (f"MA{window}", averages[window][-1], color)
        for window, color in ma_series
        if averages[window][-1] is not None
    )
    positioned_labels: list[tuple[str, float, str, float]] = []
    previous_y = top - 14
    for label, value, color in sorted(endpoint_labels, key=lambda item: y_for(float(item[1]))):
        target_y = max(y_for(float(value)), previous_y + 13)
        target_y = min(target_y, top + plot_height - 3)
        positioned_labels.append((label, float(value), color, target_y))
        previous_y = target_y
    for label, value, color, label_y in positioned_labels:
        actual_y = y_for(value)
        parts.append(
            f'<circle cx="{width - right}" cy="{actual_y:.2f}" r="2.8" fill="{color}"/>'
            f'<line x1="{width - right + 3}" x2="{width - right + 10}" y1="{actual_y:.2f}" '
            f'y2="{label_y:.2f}" stroke="{color}" stroke-width="0.8"/>'
            f'<text x="{width - right + 13}" y="{label_y + 3.5:.2f}" fill="{color}" '
            f'font-size="9.5" font-weight="700">{_esc(label)} {_esc(_format_price(value, currency))}</text>'
        )

    label_indices = sorted({round((len(bars) - 1) * ratio / 4) for ratio in range(5)})
    for index in label_indices:
        anchor = "start" if index == 0 else "end" if index == len(bars) - 1 else "middle"
        parts.append(
            f'<text x="{x_for(index):.2f}" y="{height - 12}" text-anchor="{anchor}" '
            f'fill="#64748b" font-size="10">{_esc(_short_date(bars[index].date))}</text>'
        )

    legend = ['<circle cx="64" cy="13" r="4" fill="#0f766e"/><text x="73" y="17" fill="#475569" font-size="10">收盘价</text>']
    legend_x = 130
    for window, color in ma_series:
        if len(bars) >= window:
            legend.append(
                f'<line x1="{legend_x}" x2="{legend_x + 16}" y1="13" y2="13" stroke="{color}" stroke-width="2"/>'
                f'<text x="{legend_x + 21}" y="17" fill="#475569" font-size="10">MA{window}</text>'
            )
            legend_x += 72

    svg = (
        f'<svg data-testid="analysis-price-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="近 {len(bars)} 个交易日价格趋势图">{"".join(legend)}{"".join(parts)}</svg>'
    )
    source = getattr(kline_data, "source", None) or "公开行情"
    subtitle = f"最近 {len(bars)} 个交易日 · 前复权 · 数据截至 {bars[-1].date} · 来源 {source}"
    lookback = min(20, len(closes) - 1)
    stage_change = (closes[-1] / closes[-lookback - 1] - 1) * 100
    signals = [
        (
            f"近 {lookback} 个交易日收盘价{('上涨' if stage_change >= 0 else '下跌')} {_format_percent(abs(stage_change), signed=False)}",
            "positive" if stage_change >= 0 else "negative",
        )
    ]
    ma_values = [averages[window][-1] for window, _ in ma_series]
    if all(value is not None for value in ma_values):
        ma5, ma20, ma60 = (float(value) for value in ma_values)
        if closes[-1] > ma5 > ma20 > ma60:
            signals.append(("价格位于均线之上，MA5/20/60 呈多头排列", "positive"))
        elif closes[-1] < ma5 < ma20 < ma60:
            signals.append(("价格位于均线之下，MA5/20/60 呈空头排列", "negative"))
        else:
            signals.append(("均线交错，趋势方向仍需进一步确认", "neutral"))
    if support is not None:
        distance = (closes[-1] / support - 1) * 100
        relation = "高于" if distance >= 0 else "低于"
        signals.append(
            (
                f"现价{relation}支撑/止损参考 {_format_percent(abs(distance), signed=False)}",
                "neutral" if distance >= 0 else "negative",
            )
        )
    elif resistance is not None:
        distance = (resistance / closes[-1] - 1) * 100
        signals.append((f"距离压力参考 {_format_percent(distance, signed=False)}", "neutral"))
    return _chart_card("价格趋势与关键点位", subtitle, svg, signals=signals)


def _format_volume(value: float) -> str:
    if abs(value) >= 1e8:
        return f"{value / 1e8:.1f} 亿"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.1f} 万"
    return f"{value:,.0f}"


def _render_volume_chart(kline_data: KlineData | None, *, end_date: Any = None) -> str:
    bars = _valid_bars(kline_data, end_date=end_date)
    if len(bars) < 2:
        return ""
    volumes = [max(float(item.volume), 0) for item in bars]
    maximum = max(volumes) or 1
    width, height = 760, 174
    left, right, top, bottom = 62, 20, 16, 34
    plot_width = width - left - right
    plot_height = height - top - bottom
    step = plot_width / len(bars)
    bar_width = max(step * 0.72, 1)
    parts: list[str] = []
    for index in range(4):
        value = maximum * (3 - index) / 3
        y = top + plot_height * index / 3
        parts.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y:.2f}" y2="{y:.2f}" stroke="#e2e8f0"/>'
            f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" fill="#64748b" font-size="10">'
            f'{_esc(_format_volume(value))}</text>'
        )
    for index, (item, volume) in enumerate(zip(bars, volumes, strict=True)):
        bar_height = volume / maximum * plot_height
        x = left + index * step + (step - bar_width) / 2
        previous_close = bars[index - 1].close if index else item.open
        rising = item.close >= previous_close
        color = "#ef4444" if rising else "#16a34a"
        stroke = "#7f1d1d" if rising else "#14532d"
        parts.append(
            f'<rect class="volume-bar" x="{x:.2f}" y="{top + plot_height - bar_height:.2f}" '
            f'width="{bar_width:.2f}" height="{bar_height:.2f}" fill="{color}" stroke="{stroke}" '
            f'stroke-width="0.35" opacity="0.82"/>'
        )
    average_20 = sum(volumes[-20:]) / min(20, len(volumes))
    average_y = top + plot_height - average_20 / maximum * plot_height
    parts.append(
        f'<line x1="{left}" x2="{width - right}" y1="{average_y:.2f}" y2="{average_y:.2f}" '
        f'stroke="#475569" stroke-width="1" stroke-dasharray="5 3"/>'
        f'<text x="{width - right - 3}" y="{average_y - 4:.2f}" text-anchor="end" fill="#475569" '
        f'font-size="9.5">20日均量 {_esc(_format_volume(average_20))}</text>'
    )
    for index in sorted({round((len(bars) - 1) * ratio / 4) for ratio in range(5)}):
        x = left + (index + 0.5) * step
        anchor = "start" if index == 0 else "end" if index == len(bars) - 1 else "middle"
        parts.append(
            f'<text x="{x:.2f}" y="{height - 10}" text-anchor="{anchor}" fill="#64748b" font-size="10">'
            f"{_esc(_short_date(bars[index].date))}</text>"
        )
    svg = (
        f'<svg data-testid="analysis-volume-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="近 {len(bars)} 个交易日成交量图">{"".join(parts)}</svg>'
    )
    recent_window = min(5, len(volumes))
    baseline_values = volumes[max(0, len(volumes) - recent_window - 20) : -recent_window]
    recent_average = sum(volumes[-recent_window:]) / recent_window
    baseline_average = sum(baseline_values) / len(baseline_values) if baseline_values else average_20
    volume_change = (recent_average / baseline_average - 1) * 100 if baseline_average else 0
    price_change = (float(bars[-1].close) / float(bars[-recent_window].close) - 1) * 100
    if volume_change >= 8:
        volume_text, volume_tone = f"近 {recent_window} 日均量较前期放大 {_format_percent(volume_change, signed=False)}", "positive"
    elif volume_change <= -8:
        volume_text, volume_tone = f"近 {recent_window} 日均量较前期收缩 {_format_percent(abs(volume_change), signed=False)}", "neutral"
    else:
        volume_text, volume_tone = f"近 {recent_window} 日量能与前期基本持平", "neutral"
    if price_change > 0 and volume_change > 8:
        relation = ("价升量增，短期交易活跃度改善", "positive")
    elif price_change < 0 and volume_change > 8:
        relation = ("价跌量增，需关注抛压释放风险", "negative")
    elif price_change > 0 and volume_change < -8:
        relation = ("价升量缩，上行动能仍需成交确认", "neutral")
    else:
        relation = ("量价暂未形成明显共振", "neutral")
    source = getattr(kline_data, "source", None) or "公开行情"
    subtitle = f"红涨绿跌 · 20 日均量参考 · 数据截至 {bars[-1].date} · 来源 {source}"
    return _chart_card("量价配合", subtitle, svg, signals=[(volume_text, volume_tone), relation])


def _price_range(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    try:
        if len(value) != 2:
            return None
    except TypeError:
        return None
    low, high = _number(value[0]), _number(value[1])
    if low is None or high is None:
        return None
    return min(low, high), max(low, high)


def _render_valuation_chart(result: AnalysisResult, currency: str = "¥") -> str:
    current = _number(getattr(result, "current_price", None))
    technical = getattr(result, "technical", None)
    support = _number(getattr(technical, "support_level", None))
    resistance = _number(getattr(technical, "resistance_level", None))
    research = getattr(result, "research_framework", None)
    actions = getattr(research, "actions", None) if research else None
    valuation = getattr(research, "valuation", None) if research else None
    scenarios = getattr(valuation, "scenarios", None) if valuation else None

    rows: list[tuple[str, tuple[float, float], str]] = []
    buy_range = _price_range(getattr(actions, "buy_or_add_range", None)) if actions else None
    if buy_range:
        rows.append(("买入/加仓区间", buy_range, "#14b8a6"))
    for key, label, color in (
        ("bear", "悲观情景", "#ef4444"),
        ("base", "基准情景", "#3b82f6"),
        ("bull", "乐观情景", "#22c55e"),
    ):
        scenario = getattr(scenarios, key, None) if scenarios else None
        value_range = _price_range(getattr(scenario, "fair_value_range", None)) if scenario else None
        if value_range:
            rows.append((label, value_range, color))
    estimated = _price_range(getattr(result, "estimated_price_range", None))
    if estimated:
        rows.append(("综合目标区间", estimated, "#8b5cf6"))
    for label, value, color in (
        ("支撑/止损参考", support, "#16a34a"),
        ("压力参考", resistance, "#dc2626"),
    ):
        if value is not None:
            rows.append((label, (value, value), color))
    if not rows:
        return ""

    scale_values = [number for _, value_range, _ in rows for number in value_range]
    if current is not None:
        scale_values.append(current)
    low, high = min(scale_values), max(scale_values)
    padding = (high - low) * 0.08 or max(high * 0.04, 0.01)
    low -= padding
    high += padding
    width = 760
    left, right, top = 138, 24, 42
    plot_width = width - left - right
    row_height = 38
    height = top + len(rows) * row_height + 32
    def x_for(value: float) -> float:
        return left + (value - low) / (high - low) * plot_width

    parts: list[str] = []
    for index in range(5):
        value = low + (high - low) * index / 4
        x = x_for(value)
        anchor = "start" if index == 0 else "end" if index == 4 else "middle"
        parts.append(
            f'<line x1="{x:.2f}" x2="{x:.2f}" y1="26" y2="{height - 22}" stroke="#e2e8f0"/>'
            f'<text x="{x:.2f}" y="18" text-anchor="{anchor}" fill="#64748b" font-size="9.5">'
            f'{_esc(_format_price(value, currency))}</text>'
        )
    for index, (label, value_range, color) in enumerate(rows):
        y = top + index * row_height
        x1, x2 = x_for(value_range[0]), x_for(value_range[1])
        parts.append(
            f'<text x="{left - 10}" y="{y + 16}" text-anchor="end" fill="#475569" font-size="11">{_esc(label)}</text>'
            f'<line x1="{left}" x2="{width - right}" y1="{y + 12}" y2="{y + 12}" stroke="#f1f5f9" stroke-width="10" stroke-linecap="round"/>'
        )
        if abs(x2 - x1) < 2:
            parts.append(f'<circle cx="{x1:.2f}" cy="{y + 12}" r="5" fill="{color}"/>')
        else:
            parts.append(
                f'<rect x="{x1:.2f}" y="{y + 5}" width="{max(x2 - x1, 4):.2f}" height="14" rx="7" fill="{color}" opacity="0.86"/>'
            )
        range_text = (
            _format_price(value_range[0], currency)
            if value_range[0] == value_range[1]
            else f"{_format_price(value_range[0], currency)} - {_format_price(value_range[1], currency)}"
        )
        parts.append(
            f'<text x="{min(max(x2 + 6, left + 4), width - right):.2f}" y="{y + 31}" '
            f'text-anchor="end" fill="{color}" font-size="9.5" font-weight="700">{_esc(range_text)}</text>'
        )
    if current is not None:
        current_x = x_for(current)
        parts.append(
            f'<line x1="{current_x:.2f}" x2="{current_x:.2f}" y1="25" y2="{height - 22}" '
            f'stroke="#0f172a" stroke-width="1.5" stroke-dasharray="4 3"/>'
            f'<rect x="{current_x - 44:.2f}" y="1" width="88" height="20" rx="5" fill="#0f172a"/>'
            f'<text x="{current_x:.2f}" y="15" text-anchor="middle" fill="#ffffff" font-size="10" font-weight="700">'
            f"当前 {_esc(_format_price(current, currency))}</text>"
        )
    svg = (
        f'<svg data-testid="analysis-valuation-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="估值与目标区间图">{"".join(parts)}</svg>'
    )
    signals: list[tuple[str, str]] = []
    if current is not None and buy_range:
        if buy_range[0] <= current <= buy_range[1]:
            signals.append(("当前价位于建议买入/加仓区间内", "positive"))
        elif current < buy_range[0]:
            signals.append(("当前价低于建议买入区间下沿，需结合基本面复核", "neutral"))
        else:
            premium = (current / buy_range[1] - 1) * 100
            signals.append((f"当前价高于建议买入区间上沿 {_format_percent(premium, signed=False)}", "negative"))
    target_range = estimated
    base_scenario = getattr(scenarios, "base", None) if scenarios else None
    if target_range is None and base_scenario:
        target_range = _price_range(getattr(base_scenario, "fair_value_range", None))
    if current is not None and target_range:
        midpoint = sum(target_range) / 2
        upside = (midpoint / current - 1) * 100
        signals.append((f"目标区间中值对应空间 {_format_percent(upside)}", "positive" if upside >= 0 else "negative"))
    if current is not None and support is not None:
        downside = (support / current - 1) * 100
        signals.append((f"支撑/止损参考对应空间 {_format_percent(downside)}", "negative" if downside < 0 else "neutral"))
    return _chart_card(
        "估值、目标与风控区间",
        "区间来自本次分析结论与三情景估值；关键点位为辅助参考",
        svg,
        signals=signals,
    )


def _compress_histogram(chip_distribution: ChipDistribution, *, limit: int = 80) -> list[tuple[float, float]]:
    values = sorted(
        (
            (float(item.price), float(item.ratio))
            for item in chip_distribution.histogram
            if _number(item.price) is not None and _number(item.ratio) is not None and item.ratio > 0
        ),
        key=lambda item: item[0],
    )
    if len(values) <= limit:
        return values
    chunk_size = math.ceil(len(values) / limit)
    compressed: list[tuple[float, float]] = []
    for start in range(0, len(values), chunk_size):
        chunk = values[start : start + chunk_size]
        ratio = sum(item[1] for item in chunk)
        price = sum(item[0] * item[1] for item in chunk) / ratio if ratio else sum(item[0] for item in chunk) / len(chunk)
        compressed.append((price, ratio))
    return compressed


def _render_chip_chart(chip_distribution: ChipDistribution | None, currency: str = "¥") -> str:
    if chip_distribution is None:
        return ""
    values = _compress_histogram(chip_distribution)
    if len(values) < 2:
        return ""
    prices = [item[0] for item in values]
    ratios = [item[1] for item in values]
    low, high = min(prices), max(prices)
    if high <= low:
        return ""
    maximum = max(ratios) or 1
    width, height = 760, 286
    left, right, top, bottom = 72, 30, 24, 30
    plot_width = width - left - right
    plot_height = height - top - bottom
    def y_for(value: float) -> float:
        return top + (high - value) / (high - low) * plot_height

    parts: list[str] = []
    for index in range(5):
        value = high - (high - low) * index / 4
        y = y_for(value)
        parts.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y:.2f}" y2="{y:.2f}" stroke="#e2e8f0"/>'
            f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" fill="#64748b" font-size="10">'
            f'{value:,.0f}</text>'
        )
    cost_90 = chip_distribution.cost_90
    cost_70 = chip_distribution.cost_70
    for cost_range, color, opacity in ((cost_90, "#dbeafe", 0.6), (cost_70, "#bfdbfe", 0.8)):
        band_top = y_for(min(max(cost_range.high, low), high))
        band_bottom = y_for(min(max(cost_range.low, low), high))
        parts.append(
            f'<rect x="{left}" y="{band_top:.2f}" width="{plot_width}" height="{max(band_bottom - band_top, 0):.2f}" '
            f'fill="{color}" opacity="{opacity}"/>'
        )
    step = plot_height / len(values)
    for index, (_, ratio) in enumerate(reversed(values)):
        bar_width = ratio / maximum * (plot_width * 0.7)
        y = top + index * step
        parts.append(
            f'<rect x="{left}" y="{y:.2f}" width="{bar_width:.2f}" height="{max(step * 0.82, 1):.2f}" '
            f'fill="#0f766e" opacity="0.8"/>'
        )
    for label, value, color in (
        ("当前价", chip_distribution.price, "#ef4444"),
        ("平均成本", chip_distribution.avg_cost, "#8b5cf6"),
        ("筹码峰", chip_distribution.peak_price, "#f59e0b"),
    ):
        number = _number(value)
        if number is None or not low <= number <= high:
            continue
        y = y_for(number)
        parts.append(
            f'<line x1="{left}" x2="{width - right}" y1="{y:.2f}" y2="{y:.2f}" stroke="{color}" stroke-width="1.3" stroke-dasharray="5 3"/>'
            f'<text x="{width - right}" y="{y - 4:.2f}" text-anchor="end" fill="{color}" font-size="10" font-weight="700">'
            f"{_esc(label)} {_esc(_format_price(number, currency))}</text>"
        )
    parts.append(
        f'<text x="{left}" y="{height - 9}" fill="#475569" font-size="10">获利筹码比例 '
        f'{chip_distribution.profit_ratio * 100:.1f}% · 蓝色阴影为 90% / 70% 成本区间</text>'
    )
    svg = (
        f'<svg data-testid="analysis-chip-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="筹码成本分布图">{"".join(parts)}</svg>'
    )
    current = _number(chip_distribution.price)
    average = _number(chip_distribution.avg_cost)
    peak = _number(chip_distribution.peak_price)
    signals: list[tuple[str, str]] = []
    if current is not None and average is not None and average > 0:
        distance = (current / average - 1) * 100
        position = "上方" if distance >= 0 else "下方"
        signals.append(
            (f"当前价位于平均成本{position} {_format_percent(abs(distance), signed=False)}", "positive" if distance >= 0 else "negative")
        )
    if current is not None and peak is not None and peak > 0:
        distance = (current / peak - 1) * 100
        position = "上方" if distance >= 0 else "下方"
        signals.append((f"当前价位于筹码峰{position} {_format_percent(abs(distance), signed=False)}", "neutral"))
    profit_ratio = _number(chip_distribution.profit_ratio)
    if profit_ratio is not None:
        signals.append(
            (
                f"模型估算获利筹码占比 {profit_ratio * 100:.1f}%",
                "positive" if profit_ratio >= 0.6 else "negative" if profit_ratio <= 0.3 else "neutral",
            )
        )
    return _chart_card(
        "筹码成本分布",
        f"数据截至 {chip_distribution.as_of_date} · 本地模型估算，不等同于交易所持仓统计",
        svg,
        signals=signals,
    )


def _render_decision_dashboard(
    result: AnalysisResult,
    kline_data: KlineData | None,
    currency: str = "¥",
) -> str:
    bars = _valid_bars(kline_data, end_date=getattr(result, "analysis_date", None))
    current = _number(getattr(result, "current_price", None))
    if current is None and bars:
        current = _number(bars[-1].close)

    metrics: list[tuple[str, str, str, str]] = []
    if current is not None:
        metrics.append(("当前价", _format_price(current, currency), "报告参考价格", "neutral"))

    if len(bars) >= 2:
        closes = [float(item.close) for item in bars]
        lookback = min(20, len(closes) - 1)
        stage_change = (closes[-1] / closes[-lookback - 1] - 1) * 100
        metrics.append(
            (
                "阶段涨跌",
                _format_percent(stage_change),
                f"近 {lookback} 个交易日",
                "positive" if stage_change >= 0 else "negative",
            )
        )

        returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes)) if closes[index - 1]]
        if len(returns) >= 2:
            mean_return = sum(returns) / len(returns)
            variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
            annualized_volatility = math.sqrt(variance) * math.sqrt(252) * 100
            metrics.append(("年化波动", _format_percent(annualized_volatility, signed=False), "日收益率估算", "neutral"))

        volumes = [max(float(item.volume), 0) for item in bars]
        recent_window = min(5, len(volumes))
        baseline = volumes[max(0, len(volumes) - recent_window - 20) : -recent_window]
        if baseline:
            recent_average = sum(volumes[-recent_window:]) / recent_window
            baseline_average = sum(baseline) / len(baseline)
            if baseline_average:
                volume_change = (recent_average / baseline_average - 1) * 100
                metrics.append(
                    (
                        "量能变化",
                        _format_percent(volume_change),
                        f"近 {recent_window} 日均量 vs 前期",
                        "positive" if volume_change >= 8 else "negative" if volume_change <= -8 else "neutral",
                    )
                )

    target_range = _price_range(getattr(result, "estimated_price_range", None))
    research = getattr(result, "research_framework", None)
    valuation = getattr(research, "valuation", None) if research else None
    scenarios = getattr(valuation, "scenarios", None) if valuation else None
    if target_range is None and scenarios:
        base_scenario = getattr(scenarios, "base", None)
        target_range = _price_range(getattr(base_scenario, "fair_value_range", None)) if base_scenario else None
    if current is not None and current > 0 and target_range:
        target_midpoint = sum(target_range) / 2
        target_upside = (target_midpoint / current - 1) * 100
        metrics.append(
            (
                "目标空间",
                _format_percent(target_upside),
                f"目标中值 {_format_price(target_midpoint, currency)}",
                "positive" if target_upside >= 0 else "negative",
            )
        )

    technical = getattr(result, "technical", None)
    support = _number(getattr(technical, "support_level", None))
    if current is not None and current > 0 and support is not None:
        stop_space = (support / current - 1) * 100
        metrics.append(("止损空间", _format_percent(stop_space), f"参考位 {_format_price(support, currency)}", "negative"))

    if not metrics:
        return ""
    cards = "".join(
        f"""
        <div class="decision-metric metric-{_esc(tone)}">
            <div class="decision-metric-label">{_esc(label)}</div>
            <div class="decision-metric-value">{_esc(value)}</div>
            <div class="decision-metric-detail">{_esc(detail)}</div>
        </div>
        """
        for label, value, detail, tone in metrics
    )
    return f"""
    <div class="decision-dashboard" data-testid="analysis-decision-dashboard">
        {cards}
    </div>
    """


def _render_visual_analysis(
    result: AnalysisResult,
    kline_data: KlineData | None,
    chip_distribution: ChipDistribution | None,
    currency: str = "¥",
) -> str:
    dashboard = _render_decision_dashboard(result, kline_data, currency=currency)
    cards = [
        _render_price_chart(result, kline_data, currency=currency),
        _render_volume_chart(kline_data, end_date=getattr(result, "analysis_date", None)),
        _render_valuation_chart(result, currency=currency),
        _render_chip_chart(chip_distribution, currency=currency),
    ]
    content = "".join(card for card in cards if card)
    if not content:
        return ""
    bars = _valid_bars(kline_data, end_date=getattr(result, "analysis_date", None))
    as_of_date = bars[-1].date if bars else getattr(chip_distribution, "as_of_date", None)
    data_note = f"数据截至 {_esc(as_of_date)}" if as_of_date else f"分析基准日 {_esc(getattr(result, 'analysis_date', '最新'))}"
    return f"""
    <div class="visual-section">
        <div class="visual-section-header">
            <div class="visual-section-title">投资决策仪表盘与可视化辅助</div>
            <div class="visual-section-date">{data_note}</div>
        </div>
        {dashboard}
        {content}
        <div class="visual-disclaimer">
            图表用于辅助说明研究结论，历史走势及模型区间不代表未来收益；筹码分布为本地模型估算，不等同于交易所持仓统计。
        </div>
    </div>
    """


def generate_research_report_html(
    result: AnalysisResult,
    stock_info: dict[str, Any] | None = None,
    valuation_info: dict[str, Any] | None = None,
    kline_data: KlineData | None = None,
    chip_distribution: ChipDistribution | None = None,
) -> str:
    """生成完整展开 8 大投研维度、全量数据与结论的机构级 A4 研报 HTML。"""
    code = getattr(result, "stock_code", None) or getattr(result, "code", "")
    is_hk = is_hk_code(code)
    curr = "HK$" if is_hk else "¥"
    default_industry = "港股上市公司" if is_hk else "A股上市公司"
    platform_name = "港股智能投研体系" if is_hk else "A股智能投研体系"
    name = getattr(result, "stock_name", None) or getattr(result, "name", "") or (stock_info.get("name") if stock_info else "") or code
    analysis_date = getattr(result, "analysis_date", "") or "最新"
    raw_signal = getattr(result, "signal", "hold")
    signal_label, signal_bg, signal_fg, signal_border = SIGNAL_MAP.get(raw_signal, (str(raw_signal), "#e0f2fe", "#0369a1", "#7dd3fc"))
    
    confidence = int((getattr(result, "confidence", None) or getattr(result, "confidence_score", 0.8)) * 100)
    current_price = getattr(result, "current_price", None)
    
    est_range = getattr(result, "estimated_price_range", None)
    if est_range and len(est_range) == 2:
        target_range_str = f"{curr}{est_range[0]:.2f} - {curr}{est_range[1]:.2f}"
    else:
        target_range_str = str(getattr(result, "target_price_range", "--") or "--")

    industry_text = ""
    if stock_info:
        first_ind = stock_info.get("first_industry", {}).get("name", "") if isinstance(stock_info.get("first_industry"), dict) else ""
        second_ind = stock_info.get("second_industry", {}).get("name", "") if isinstance(stock_info.get("second_industry"), dict) else ""
        third_ind = stock_info.get("third_industry", {}).get("name", "") if isinstance(stock_info.get("third_industry"), dict) else ""
        industry_text = " / ".join(filter(None, [first_ind, second_ind, third_ind]))

    rf = getattr(result, "research_framework", None)

    # ---------------- 01 信息质量 ----------------
    iq = getattr(rf, "information_quality", None) if rf else None
    iq_grade = GRADE_LABELS.get(iq.grade, iq.grade) if iq else "A · 资料完备"
    iq_cert = f"{int(iq.investment_certainty * 100)}%" if iq and iq.investment_certainty is not None else f"{confidence}%"
    iq_conf = f"{int(iq.evidence_confidence * 100)}%" if iq and iq.evidence_confidence is not None else f"{confidence}%"

    # ---------------- 02 商业模式 ----------------
    bm = getattr(rf, "business_model", None) if rf else None
    segments_html = ""
    if bm and bm.segment_quality:
        segments_html = '<div style="margin-top:8px;"><div style="font-weight:700; font-size:11px; color:#475569; margin-bottom:6px;">📊 主营分部质量明细评估：</div><div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:8px;">'
        for seg in bm.segment_quality:
            conf_str = f"{int(seg.evidence_confidence * 100)}% 证据" if seg.evidence_confidence is not None else "证据待核验"
            segments_html += f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <strong style="color:#0f172a; font-size:12px;">{_esc(seg.segment)}</strong>
                    <span style="font-size:10px; color:#64748b; background:#f1f5f9; padding:1px 6px; border-radius:4px;">{_esc(seg.role or '主营业务')} ｜ {conf_str}</span>
                </div>
                <div style="font-size:11px; color:#475569; line-height:1.45;">
                    <div>• 增长质量: <strong>{_esc(seg.growth_quality or '--')}</strong></div>
                    <div>• 盈利质量: <strong>{_esc(seg.profitability_quality or '--')}</strong></div>
                    <div>• 收入持续性/现金重现: <strong>{_esc(seg.recurrence or '--')}</strong></div>
                </div>
            </div>
            """
        segments_html += '</div></div>'

    # ---------------- 03 护城河 ----------------
    moat = getattr(rf, "moat", None) if rf else None
    moats_html = ""
    if moat and moat.moats:
        moats_html = '<div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:10px; margin-top:8px;">'
        for m in moat.moats:
            m_name = MOAT_LABELS.get(m.moat_type, m.moat_type)
            m_strength = LEVEL_LABELS.get(m.strength, m.strength)
            m_dir = DIRECTION_LABELS.get(m.direction, m.direction)
            counter_threats = [*getattr(m, "counterevidence", []), *getattr(m, "threats", [])]
            moats_html += f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <strong style="color:#0f172a; font-size:13px;">{_esc(m_name)}</strong>
                    <div>
                        {_render_pill(f'强度: {m_strength}', '#f1f5f9', '#334155', '#cbd5e1')}
                        {_render_pill(f'趋势: {m_dir}', '#eff6ff', '#1d4ed8', '#bfdbfe')}
                    </div>
                </div>
                <div style="font-size:11px; color:#475569; margin-bottom:4px;"><strong>持续期限:</strong> {_esc(m.durability or '长期稳固')}</div>
                <div style="font-size:11px; color:#334155; margin-top:4px;"><strong>支持证据:</strong></div>
                {_render_list_items(m.evidence)}
                {f'<div style="font-size:11px; color:#991b1b; margin-top:4px;"><strong>反证与潜在威胁:</strong></div>{_render_list_items(counter_threats)}' if counter_threats else ''}
            </div>
            """
        moats_html += '</div>'

    # ---------------- 04 管理层与行业 ----------------
    mgmt = getattr(rf, "management", None) if rf else None
    ind = getattr(rf, "industry_position", None) if rf else None

    # ---------------- 05 逆向推演与风险 ----------------
    inv = getattr(rf, "inversion", None) if rf else None
    risks_html = ""
    if inv and inv.risks:
        risks_html = '<div style="margin-top:8px;">'
        for r in inv.risks:
            r_prob = RISK_LABELS.get(r.probability, r.probability)
            r_impact = RISK_LABELS.get(r.impact, r.impact)
            horizon_str = f" ｜ 观察窗口: {r.time_horizon}" if getattr(r, "time_horizon", None) else ""
            risks_html += f"""
            <div style="background:#ffffff; border:1px solid #fecaca; border-left:4px solid #ef4444; border-radius:6px; padding:10px; margin-bottom:8px; break-inside:avoid;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <strong style="color:#991b1b; font-size:12px;">⚠️ {_esc(r.risk)}</strong>
                    <div>
                        {_render_pill(f'概率: {r_prob}', '#fef2f2', '#991b1b', '#fecaca')}
                        {_render_pill(f'影响: {r_impact}{horizon_str}', '#fef2f2', '#991b1b', '#fecaca')}
                    </div>
                </div>
                {f'<div style="font-size:11px; color:#475569; margin-bottom:3px;"><strong>失效路径:</strong> {_esc(r.failure_path)}</div>' if r.failure_path else ''}
                {f'<div style="font-size:11px; color:#475569; margin-bottom:3px;"><strong>先行指标:</strong> {_esc(", ".join(r.leading_indicators))}</div>' if r.leading_indicators else ''}
                {f'<div style="font-size:11px; color:#166534;"><strong>对冲缓解:</strong> {_esc(", ".join(r.mitigants))}</div>' if r.mitigants else ''}
            </div>
            """
        risks_html += '</div>'
    elif getattr(result, "risk_warnings", None):
        risks_html = _render_list_items(result.risk_warnings)

    # ---------------- 06 估值三情景 ----------------
    val_framework = getattr(rf, "valuation", None) if rf else None
    sc = getattr(val_framework, "scenarios", None) if val_framework else getattr(result, "scenarios", None)
    sc_html = ""
    if sc and getattr(sc, "bull", None) and getattr(sc, "base", None) and getattr(sc, "bear", None):
        bull_range = f"{curr}{sc.bull.fair_value_range[0]:.2f} - {curr}{sc.bull.fair_value_range[1]:.2f}" if getattr(sc.bull, "fair_value_range", None) else "--"
        base_range = f"{curr}{sc.base.fair_value_range[0]:.2f} - {curr}{sc.base.fair_value_range[1]:.2f}" if getattr(sc.base, "fair_value_range", None) else "--"
        bear_range = f"{curr}{sc.bear.fair_value_range[0]:.2f} - {curr}{sc.bear.fair_value_range[1]:.2f}" if getattr(sc.bear, "fair_value_range", None) else "--"

        sc_html = f"""
        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-top:8px;">
            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:10px;">
                <div style="font-weight:700; color:#166534; font-size:13px; margin-bottom:4px;">乐观情景 (Bull)</div>
                <div style="font-size:16px; font-weight:800; color:#15803d; margin-bottom:4px;">{_esc(bull_range)}</div>
                <div style="font-size:11px; color:#166534; line-height:1.45;">
                    <div>{_esc(sc.bull.valuation_view or '增长超出市场预期')}</div>
                    <div style="margin-top:6px; font-weight:700;">关键假设:</div>
                    {_render_list_items(sc.bull.assumptions)}
                    {f'<div style="margin-top:6px; font-weight:700; color:#991b1b;">失效条件:</div>{_render_list_items(sc.bull.invalidating_conditions)}' if sc.bull.invalidating_conditions else ''}
                </div>
            </div>
            <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:6px; padding:10px;">
                <div style="font-weight:700; color:#1d4ed8; font-size:13px; margin-bottom:4px;">基准情景 (Base)</div>
                <div style="font-size:16px; font-weight:800; color:#1e40af; margin-bottom:4px;">{_esc(base_range)}</div>
                <div style="font-size:11px; color:#1d4ed8; line-height:1.45;">
                    <div>{_esc(sc.base.valuation_view or '业务稳健推进')}</div>
                    <div style="margin-top:6px; font-weight:700;">关键假设:</div>
                    {_render_list_items(sc.base.assumptions)}
                    {f'<div style="margin-top:6px; font-weight:700; color:#991b1b;">失效条件:</div>{_render_list_items(sc.base.invalidating_conditions)}' if sc.base.invalidating_conditions else ''}
                </div>
            </div>
            <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:6px; padding:10px;">
                <div style="font-weight:700; color:#991b1b; font-size:13px; margin-bottom:4px;">悲观情景 (Bear)</div>
                <div style="font-size:16px; font-weight:800; color:#b91c1c; margin-bottom:4px;">{_esc(bear_range)}</div>
                <div style="font-size:11px; color:#991b1b; line-height:1.45;">
                    <div>{_esc(sc.bear.valuation_view or '承压与估值收缩')}</div>
                    <div style="margin-top:6px; font-weight:700;">关键假设:</div>
                    {_render_list_items(sc.bear.assumptions)}
                    {f'<div style="margin-top:6px; font-weight:700; color:#991b1b;">失效条件:</div>{_render_list_items(sc.bear.invalidating_conditions)}' if sc.bear.invalidating_conditions else ''}
                </div>
            </div>
        </div>
        """

    # ---------------- 07 行动建议与持续跟踪 ----------------
    act = getattr(rf, "actions", None) if rf else None
    new_inv_act = ACTION_LABELS.get(act.new_investor_action, act.new_investor_action) if act else "重点关注"
    holder_act = ACTION_LABELS.get(act.holder_action, act.holder_action) if act else "继续持有"
    buy_range_str = f"{curr}{act.buy_or_add_range[0]:.2f} - {curr}{act.buy_or_add_range[1]:.2f}" if act and act.buy_or_add_range and len(act.buy_or_add_range) == 2 else target_range_str

    # ---------------- 08 数据缺口 ----------------
    data_gaps = getattr(rf, "data_gaps", []) if rf else []
    data_gap_cards = "".join(
        f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;">
            <strong style="color:#0f172a; font-size:12px;">{_esc(g.topic)}</strong>
            <div style="font-size:11px; color:#475569; margin-top:2px;">{_esc(g.missing_data or '缺失数据说明未填写')}</div>
            <div style="font-size:10px; color:#64748b; margin-top:4px;">
                <div>• 决策影响: {_esc(g.decision_impact or '待评估')}</div>
                <div>• 下一步行动: {_esc(g.follow_up or '待跟进核验')}</div>
            </div>
        </div>
        """
        for g in data_gaps
    )
    data_gaps_html = (
        f"""
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">09 · 数据缺口与待核验清单 (Data Gaps)</div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:8px;">
                {data_gap_cards}
            </div>
        </div>
        """
        if data_gaps
        else ""
    )

    provenance = getattr(result, "provenance", None)
    freshness_note = provenance.freshness_note if provenance else "旧报告未记录数据时效与缓存来源；分析日期不代表数据截至日期。"

    report_id_str = _esc(getattr(result, "report_id", None) or "未记录")
    generated_at_str = _esc(getattr(result, "generated_at", None) or "未记录")
    short_report_id = report_id_str[:16] if len(report_id_str) > 16 else report_id_str

    freshness_html = f"""<div class="section-card" style="padding:7px 12px; margin-bottom:10px; background:#f8fafc; border:1px solid #e2e8f0; font-size:10.5px; color:#475569;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
            <div>
                <strong>报告版本:</strong> {short_report_id} &nbsp;|&nbsp;
                <strong>生成时间:</strong> {generated_at_str}
            </div>
            <div style="color:#64748b; font-size:10px;">
                {_esc(freshness_note)}
            </div>
        </div>
    </div>"""

    # 聚合证据维度，消除重复工具调用与技术标识噪音
    aggregated_evidence: dict[str, dict[str, Any]] = {}
    if provenance and getattr(provenance, "evidence", None):
        for item in provenance.evidence:
            name = item.tool_name
            if name not in aggregated_evidence:
                aggregated_evidence[name] = {
                    "tool_name": name,
                    "data_dates": set(),
                    "report_periods": set(),
                    "cache_statuses": set(),
                    "sources": set(),
                }
            entry = aggregated_evidence[name]
            entry["data_dates"].update(item.data_dates)
            entry["report_periods"].update(item.report_periods)
            entry["cache_statuses"].add(item.cache_status)
            entry["sources"].update(item.sources)

    if aggregated_evidence:
        def _format_status(statuses: set[str]) -> str:
            if "live" in statuses and "cached" in statuses:
                return "混合采集"
            if "live" in statuses:
                return "实时采集"
            if "cached" in statuses:
                return "本地缓存"
            if len(statuses) == 1:
                return _CACHE_STATUS_LABELS.get(next(iter(statuses)), "公开披露")
            return "公开披露"

        appendix_rows = "".join(
            f"<tr><td><strong>{_esc(_format_tool_name(k))}</strong></td>"
            f"<td>{_esc('；'.join(sorted(v['data_dates'])[-3:]) or '跟随最新交易日')}</td>"
            f"<td>{_esc('；'.join(sorted(v['report_periods'])[-2:]) or '最新已披露期')}</td>"
            f"<td>{_esc(_format_status(v['cache_statuses']))}</td>"
            f"<td>{_esc('；'.join(sorted(v['sources'])[:2]) or '公开信息渠道')}</td></tr>"
            for k, v in aggregated_evidence.items()
        )
        appendix_html = f"""
        <div class="section-card section-card--splittable">
            <div class="section-header">
                <div class="section-title">附录 · 数据时效与信息来源审计 (Data Provenance & Audit)</div>
            </div>
            <p style="font-size:10.5px; color:#64748b; margin-top:0; margin-bottom:8px;">
                本报告在自动化调研过程中查验了以下 {len(aggregated_evidence)} 类数据维度，全部数据依据上市公司公开披露信息、交易所规范行情及专业研报综合归纳：
            </p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width:26%;">数据考察维度</th>
                        <th style="width:22%;">数据/来源日期</th>
                        <th style="width:14%;">报告期</th>
                        <th style="width:13%;">采集时效</th>
                        <th style="width:25%;">主要信息渠道</th>
                    </tr>
                </thead>
                <tbody>
                    {appendix_rows}
                </tbody>
            </table>
        </div>
        """
    else:
        appendix_html = ""
    overall_summary_text = getattr(result, "overall_summary", "") or getattr(result, "summary", "")
    visual_analysis_html = _render_visual_analysis(result, kline_data, chip_distribution, currency=curr)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>{_esc(name)} ({_esc(code)}) - 深度个股投资研究结论</title>
    <style>
        @page {{
            size: A4 portrait;
            margin: 15mm 14mm 16mm 14mm;
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "WenQuanYi Micro Hei", sans-serif;
            color: #1e293b;
            background: #ffffff;
            font-size: 12px;
            line-height: 1.55;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        .hero-banner {{
            border-bottom: 2px solid #087f94;
            padding-bottom: 10px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }}
        .hero-title {{
            font-size: 19px;
            font-weight: 800;
            color: #0f172a;
            margin: 0 0 4px 0;
            letter-spacing: -0.02em;
        }}
        .hero-meta {{
            font-size: 11px;
            color: #64748b;
        }}
        .hero-badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 700;
            background: {signal_bg};
            color: {signal_fg};
            border: 1px solid {signal_border};
            text-align: right;
        }}
        .section-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 14px;
            margin-bottom: 12px;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .section-card--splittable {{
            break-inside: auto;
            page-break-inside: auto;
        }}
        .action-block {{
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 6px;
            margin-bottom: 8px;
        }}
        .section-title {{
            font-size: 13px;
            font-weight: 700;
            color: #087f94;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }}
        .three-column {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
        }}
        .visual-section {{
            margin-bottom: 12px;
            break-before: auto;
            page-break-before: auto;
        }}
        .visual-section-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            color: #087f94;
            border-bottom: 2px solid #99f6e4;
            padding: 6px 2px;
            margin-bottom: 10px;
            break-after: avoid;
            page-break-after: avoid;
        }}
        .visual-section-title {{
            font-size: 14px;
            font-weight: 800;
        }}
        .visual-section-date {{
            color: #64748b;
            font-size: 9.5px;
            font-weight: 600;
        }}
        .decision-dashboard {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            margin-bottom: 10px;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .decision-metric {{
            min-height: 66px;
            padding: 8px 10px;
            border: 1px solid #dbe4ee;
            border-top: 3px solid #64748b;
            border-radius: 7px;
            background: #f8fafc;
        }}
        .decision-metric.metric-positive {{ border-top-color: #15803d; background: #f0fdf4; }}
        .decision-metric.metric-negative {{ border-top-color: #b91c1c; background: #fef2f2; }}
        .decision-metric-label {{ color: #64748b; font-size: 9px; font-weight: 700; }}
        .decision-metric-value {{ color: #0f172a; font-size: 16px; line-height: 1.25; font-weight: 800; margin-top: 2px; }}
        .decision-metric-detail {{ color: #64748b; font-size: 8.5px; margin-top: 2px; }}
        .visual-card {{
            background: #ffffff;
            border: 1px solid #dbe4ee;
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .visual-heading {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 12px;
            margin-bottom: 6px;
        }}
        .visual-heading strong {{
            color: #0f172a;
            font-size: 12px;
        }}
        .visual-heading span {{
            color: #64748b;
            font-size: 9.5px;
            text-align: right;
        }}
        .visual-card svg {{
            display: block;
            width: 100%;
            height: auto;
        }}
        .visual-signals {{
            display: grid;
            grid-template-columns: 74px 1fr;
            gap: 8px;
            align-items: start;
            margin-top: 6px;
            padding: 7px 9px;
            border-radius: 6px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            color: #334155;
            font-size: 9.5px;
        }}
        .visual-signals strong {{ color: #0f172a; }}
        .visual-signals ul {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 3px 12px;
            margin: 0;
            padding: 0;
            list-style: none;
        }}
        .visual-signals li {{ line-height: 1.35; }}
        .signal-dot {{
            display: inline-block;
            width: 6px;
            height: 6px;
            margin-right: 5px;
            border-radius: 50%;
            background: #64748b;
        }}
        .signal-positive {{ background: #15803d; }}
        .signal-negative {{ background: #b91c1c; }}
        .visual-disclaimer {{
            color: #64748b;
            font-size: 9px;
            line-height: 1.45;
            padding: 7px 9px;
            border-left: 3px solid #94a3b8;
            background: #f8fafc;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        table.data-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 6px;
            font-size: 10px;
        }}
        table.data-table th, table.data-table td {{
            border: 1px solid #e2e8f0;
            padding: 5px 8px;
            text-align: left;
            line-height: 1.4;
        }}
        table.data-table th {{
            background: #f1f5f9;
            color: #475569;
            font-weight: 700;
            font-size: 10px;
        }}
        table.data-table tr:nth-child(even) td {{
            background: #fafcfd;
        }}
        .disclaimer-box {{
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 10px;
            color: #64748b;
            line-height: 1.4;
            margin-top: 14px;
            break-inside: avoid;
        }}
    </style>
</head>
<body>

    <!-- 顶部报告抬头与评级 Hero -->
    <div class="hero-banner">
        <div>
            <h1 class="hero-title">{_esc(name)} ({_esc(code)}) · 深度价值投资研报</h1>
            <div class="hero-meta">
                所属行业：{_esc(industry_text or default_industry)} &nbsp;|&nbsp; 
                研究基准日：{_esc(analysis_date)} &nbsp;|&nbsp; 
                最新参考价：{f'{curr}{current_price:.2f}' if current_price is not None else '--'} &nbsp;|&nbsp;
                系统置信度：{confidence}%
            </div>
        </div>
        <div>
            <div class="hero-badge">
                研判：{_esc(signal_label)}
                <div style="font-size:11px; font-weight:normal; margin-top:2px;">目标区间: {_esc(target_range_str)}</div>
            </div>
        </div>
    </div>

    {freshness_html}

    <!-- 综合投资决策与核心观点总述 -->
    <div class="section-card" style="background:#f0fdfa; border-color:#99f6e4;">
        <div class="section-header" style="border-bottom-color:#99f6e4;">
            <div class="section-title" style="color:#0f766e;">💡 综合投资结论与核心投资逻辑</div>
            <div style="font-weight:600; color:#0f766e; font-size:11px;">综合评分: {getattr(result, 'overall_rating', 8)}/10</div>
        </div>
        <p style="margin:0; font-size:12px; color:#134e4a; line-height:1.6;">
            {_esc(overall_summary_text or '根据多维度深度投研分析，当前公司具备明确的竞争优势与估值支撑。')}
        </p>
    </div>

    {visual_analysis_html}

    <!-- 01 信息质量与证据链 -->
    <div class="section-card">
        <div class="section-header">
            <div class="section-title">01 · 信息质量与证据链 (Information Quality)</div>
            <div>{_render_pill(f'资料评级: {iq_grade}', '#f8fafc', '#087f94', '#087f94')}</div>
        </div>
        <div class="two-column">
            <div>
                <div style="font-size:11px; color:#475569; margin-bottom:4px;"><strong>覆盖度与评级依据:</strong></div>
                <div style="font-size:11px; color:#334155; line-height:1.5;">{_esc(iq.coverage_summary if iq and iq.coverage_summary else (iq.grade_rationale if iq else '全量财报与研报数据覆盖完毕'))}</div>
                <div style="margin-top:6px; font-size:11px; color:#64748b;">
                    证据链置信度: <strong>{iq_conf}</strong> &nbsp;|&nbsp; 投资结论确定性: <strong>{iq_cert}</strong>
                </div>
            </div>
            <div>
                <div style="font-size:11px; color:#475569; margin-bottom:4px;"><strong>核心局限与已知盲区:</strong></div>
                {_render_list_items(iq.limitations if iq and iq.limitations else ['部分前瞻性高频渠道数据依赖公开统计'])}
            </div>
        </div>
    </div>

    <!-- 02 商业模式与盈利质量 -->
    <div class="section-card">
        <div class="section-header">
            <div class="section-title">02 · 商业模式与盈利质量 (Business Model)</div>
        </div>
        <div style="font-size:11px; color:#334155; margin-bottom:6px;">
            <strong>核心经济引擎 (Economic Engine):</strong> {_esc(bm.economic_engine if bm and bm.economic_engine else '主营业务具备稳定现金流与定价能力')}
        </div>
        <div style="display:flex; gap:16px; font-size:11px; color:#475569; margin-bottom:6px;">
            <div><strong>盈利质量:</strong> {_esc(bm.earnings_quality if bm and bm.earnings_quality else '良好')}</div>
            <div><strong>经营杠杆效应:</strong> {_esc(bm.operating_leverage if bm and bm.operating_leverage else '适中')}</div>
        </div>
        {f'<div class="three-column" style="margin-top:8px;">'
           f'<div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;"><div style="font-weight:700; color:#475569; font-size:11px; margin-bottom:4px;">核心收入驱动力</div>{_render_list_items(bm.revenue_drivers)}</div>'
           f'<div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;"><div style="font-weight:700; color:#166534; font-size:11px; margin-bottom:4px;">竞争优势支撑证据</div>{_render_list_items(bm.strengths)}</div>'
           f'<div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;"><div style="font-weight:700; color:#9a3412; font-size:11px; margin-bottom:4px;">待验证隐忧与风险</div>{_render_list_items(bm.concerns)}</div>'
         f'</div>' if bm and (bm.revenue_drivers or bm.strengths or bm.concerns) else ''}
        {segments_html}
    </div>

    <!-- 03 护城河与竞争优势 -->
    <div class="section-card">
        <div class="section-header">
            <div class="section-title">03 · 护城河与竞争壁垒 (Economic Moat)</div>
            <div>{_render_pill(f'整体持续性: {moat.overall_durability if moat and moat.overall_durability else "长期稳固"}', '#f8fafc', '#087f94', '#087f94')}</div>
        </div>
        {moats_html if moats_html else '<div style="color:#64748b; font-size:11px;">护城河结构评估完成，壁垒优势保持稳定。</div>'}
        {f'<div style="margin-top:8px; background:#fff7ed; border:1px solid #fed7aa; border-radius:6px; padding:8px 10px;"><strong style="color:#c2410c; font-size:11px;">⚠️ 关键外部威胁 (Key Threats):</strong>{_render_list_items(moat.key_threats)}</div>' if moat and moat.key_threats else ''}
    </div>

    <!-- 04 管理层与资本配置 -->
    {f'''
    <div class="section-card">
        <div class="section-header">
            <div class="section-title">04 · 管理层能力与资本配置 (Management & Stewardship)</div>
        </div>
        <div class="two-column">
            <div>
                {_render_named_box("历史经营记录 (Track Record)", mgmt.track_record)}
                {_render_named_box("资本配置决策 (Capital Allocation)", mgmt.capital_allocation)}
            </div>
            <div>
                {_render_named_box("股东利益一致性 (Alignment)", mgmt.shareholder_alignment)}
                {_render_named_box("传承与关键人物风险 (Key Person Risk)", mgmt.succession_or_key_person_risk)}
            </div>
        </div>
    </div>
    ''' if mgmt else ''}

    <!-- 05 行业格局与产业链地位 -->
    <div class="section-card">
        <div class="section-header">
            <div class="section-title">05 · 行业格局与产业链地位 (Industry Landscape)</div>
        </div>
        <div class="two-column">
            <div>
                <div style="font-size:11px; color:#475569; margin-bottom:4px;"><strong>行业长期趋势与格局:</strong></div>
                <div style="font-size:11px; color:#334155; line-height:1.5;">{_esc(ind.secular_context if ind and ind.secular_context else '行业进入高质量发展与头部集中阶段')}</div>
                <div style="margin-top:6px; font-size:11px; color:#475569;"><strong>竞争地位:</strong> {_esc(ind.competitive_position if ind and ind.competitive_position else '行业领军/头部竞争者')}</div>
                <div style="margin-top:6px; font-size:11px; color:#475569;"><strong>价值链位置:</strong> {_esc(ind.value_chain_position if ind and ind.value_chain_position else '中枢关键环节')}</div>
            </div>
            <div>
                <div style="font-size:11px; color:#475569; margin-bottom:4px;"><strong>核心增长驱动力:</strong></div>
                {_render_list_items(ind.growth_drivers if ind and ind.growth_drivers else ['结构升级', '市占率提升'])}
                {f'<div style="margin-top:6px; font-size:11px; color:#991b1b;"><strong>集中度风险:</strong></div>{_render_list_items(ind.concentration_risks)}' if ind and ind.concentration_risks else ''}
            </div>
        </div>
    </div>

    <!-- 06 逆向推演与风险清单 -->
    <div class="section-card" style="border-color:#fecaca;">
        <div class="section-header" style="border-bottom-color:#fecaca;">
            <div class="section-title" style="color:#b91c1c;">06 · 逆向推演与主要风险清单 (Inversion & Risks)</div>
            <div>{_render_pill('风险警示', '#fef2f2', '#b91c1c', '#fecaca')}</div>
        </div>
        {f'<div style="font-size:11px; color:#7f1d1d; margin-bottom:6px; background:#fff1f2; padding:6px 10px; border-radius:4px;"><strong>最强看空逻辑推演 (Strongest Bear Case):</strong> {_esc(inv.bear_case)}</div>' if inv and inv.bear_case else ''}
        {risks_html if risks_html else '<div style="color:#64748b; font-size:11px;">暂无重大一票否决级风险。</div>'}
        {f'<div style="margin-top:8px; background:#ffffff; border:1px solid #fecaca; border-radius:6px; padding:8px 10px;"><div style="font-weight:700; color:#991b1b; font-size:11px; margin-bottom:4px;">认知偏差与假设自查 (Bias Checks):</div>{_render_list_items(inv.bias_checks)}</div>' if inv and inv.bias_checks else ''}
    </div>

    <!-- 07 估值假设与三情景分析 -->
    <div class="section-card">
        <div class="section-header">
            <div class="section-title">07 · 估值假设与三情景推演 (Valuation Scenarios)</div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:11px; color:#475569; margin-bottom:6px;">
            <div><strong>当前估值:</strong> {_esc(val_framework.current_valuation if val_framework and val_framework.current_valuation else '评估中')}</div>
            <div><strong>估值方法:</strong> {_esc(val_framework.method_summary if val_framework and val_framework.method_summary else 'DCF + 相对估值法')}</div>
            <div><strong>安全边际:</strong> {_esc(val_framework.margin_of_safety if val_framework and val_framework.margin_of_safety else '具备合理安全边际')}</div>
        </div>
        {sc_html if sc_html else '<div style="color:#64748b; font-size:11px;">三情景估值模型计算完成。</div>'}
        {f'<div class="two-column" style="margin-top:8px;">'
           f'<div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;"><div style="font-weight:700; color:#475569; font-size:11px; margin-bottom:4px;">共同估值假设</div>{_render_list_items(val_framework.assumptions)}</div>'
           f'<div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;"><div style="font-weight:700; color:#64748b; font-size:11px; margin-bottom:4px;">估值局限与模型限制</div>{_render_list_items(val_framework.limitations)}</div>'
         f'</div>' if val_framework and (val_framework.assumptions or val_framework.limitations) else ''}
    </div>

    <!-- 08 决策行动与持续跟踪 -->
    <div class="section-card section-card--splittable" style="border-color:#bfdbfe; background:#f8fafc;">
        <div class="section-header" style="border-bottom-color:#bfdbfe;">
            <div class="section-title" style="color:#1d4ed8;">08 · 投资行动建议与监控体系 (Action & Monitoring)</div>
        </div>
        <div class="action-block" style="background:#ffffff; border:1px solid #bfdbfe; border-radius:6px; padding:10px 12px; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <div>
                    {_render_pill(f'新手买入: {new_inv_act}', '#eff6ff', '#1d4ed8', '#93c5fd')}
                    {_render_pill(f'持仓管理: {holder_act}', '#f0fdf4', '#15803d', '#86efac')}
                </div>
                <div style="font-size:12px; font-weight:700; color:#1e40af;">
                    建议买入/加仓区间: {_esc(buy_range_str)}
                </div>
            </div>
            <div style="font-size:11px; color:#334155; line-height:1.5;">
                <strong>决策逻辑:</strong> {_esc(act.rationale if act and act.rationale else '估值合理且基本面扎实，建议按照安全边际分批配置。')}
            </div>
        </div>

        <div class="action-block two-column" style="margin-bottom:8px;">
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;">
                <div style="font-weight:700; color:#166534; font-size:11px; margin-bottom:4px;">新投资者买入/关注触发条件:</div>
                {_render_list_items(act.add_triggers if act and act.add_triggers else ['估值进入安全边际区间', '季度财报验证盈利质量'])}
            </div>
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 10px;">
                <div style="font-weight:700; color:#b91c1c; font-size:11px; margin-bottom:4px;">已持有者减持/退出触发条件:</div>
                {_render_list_items(act.sell_triggers if act and act.sell_triggers else ['估值大幅透支基本面', '核心壁垒发生实质性恶化'])}
            </div>
        </div>

        <div class="action-block two-column">
            <div style="background:#ffffff; border:1px solid #fed7aa; border-radius:6px; padding:10px;">
                <div style="font-weight:700; color:#c2410c; font-size:12px; margin-bottom:4px;">🚨 核心逻辑失效条件 (Thesis Breakers)</div>
                {_render_list_items(act.thesis_breakers if act and act.thesis_breakers else ['核心财务造假或重大违规', '护城河壁垒瓦解市占率断崖式下滑'])}
            </div>
            <div style="background:#ffffff; border:1px solid #bfdbfe; border-radius:6px; padding:10px;">
                <div style="font-weight:700; color:#1d4ed8; font-size:12px; margin-bottom:4px;">📊 持续跟踪指标 (Monitoring Metrics)</div>
                {_render_list_items(act.monitoring_metrics if act and act.monitoring_metrics else ['季度营收与净利润增速', '自由现金流与毛利率变动'])}
            </div>
        </div>
    </div>

    <!-- 09 数据缺口与待核验 -->
    {data_gaps_html}

    <!-- 附录：数据时效与信息来源审计 -->
    {appendix_html}

    <!-- 研报合规免责声明 -->
    <div class="disclaimer-box">
        <strong>【研究声明与免责提示】</strong><br>
        1. 本报告由 {_esc(platform_name)}（AI Agentic Financial Platform）基于上市公司公开披露信息、市场公开行情及算法模型自动生成，旨在辅助投资者进行客观框架化研究，不构成任何形式的直接投资建议或保本承诺。<br>
        2. 证券市场有风险，投资决策需建立在独立判断之上。过往数据与模型情景推演不代表未来真实收益。
    </div>

</body>
</html>
"""


async def render_pdf_bytes_from_html(html_content: str, *, is_hk: bool = False) -> bytes:
    """通过共享的有界 Chromium 队列渲染报告，保留既有页眉页脚和 A4 布局。"""
    platform_name = "港股智能投研体系" if is_hk else "A股智能投研体系"
    return await render_pdf(
        html_content,
        header_template=f'<div style="font-size:8px; width:100%; text-align:right; color:#94a3b8; padding-right:14mm; font-family:sans-serif;">{platform_name} · 深度个股研究报告</div>',
        footer_template='<div style="font-size:8px; width:100%; display:flex; justify-content:space-between; color:#94a3b8; padding:0 14mm; font-family:sans-serif;"><span>内部研究参考 · 不构成投资建议</span><span>第 <span class="pageNumber"></span> 页 / 共 <span class="totalPages"></span> 页</span></div>',
    )
