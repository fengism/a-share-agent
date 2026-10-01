"""基于 Playwright 与内嵌 SVG 的每日复盘 PDF 生成服务。"""

from __future__ import annotations

import html
import logging
import math
import re
from typing import Any, Iterable

from app.infrastructure.pdf_runtime import render_pdf
from app.modules.daily_review.models import (
    DailyReviewDataSnapshot,
    DailyReviewEventImpact,
    DailyReviewResult,
    DailyReviewSection,
)

logger = logging.getLogger(__name__)

_UP = "#ef4444"
_DOWN = "#16a34a"
_NEUTRAL = "#94a3b8"
_PRIMARY = "#2563eb"
_GRID = "#e2e8f0"
_TEXT = "#475569"


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _trim_label(value: Any, limit: int = 18) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _named_values(items: Iterable[dict[str, Any]], limit: int) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = []
    for item in items:
        name = str(item.get("name") or item.get("code") or "").strip()
        value = _number(item.get("change_pct"))
        if name and value is not None:
            values.append((name, value))
        if len(values) >= limit:
            break
    return values


def _format_percent(value: float) -> str:
    return f"{'+' if value > 0 else ''}{value:.2f}%"


def _format_amount(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1e8:
        return f"{value / 1e8:.1f} 亿元"
    if absolute >= 1e4:
        return f"{value / 1e4:.1f} 万元"
    return f"{value:.0f} 元"


def _chart_card(title: str, subtitle: str, svg: str) -> str:
    return f"""
    <section class="chart-card">
      <div class="chart-heading"><strong>{_esc(title)}</strong><span>{_esc(subtitle)}</span></div>
      {svg}
    </section>
    """


def _render_breadth_chart(snapshot: DailyReviewDataSnapshot) -> str:
    raw = snapshot.market_statistics
    definitions = (
        ("上涨", "up_count", _UP),
        ("下跌", "down_count", _DOWN),
        ("平盘", "flat_count", _NEUTRAL),
        ("涨停", "limit_up_count", "#dc2626"),
        ("跌停", "limit_down_count", "#15803d"),
    )
    values = [
        (label, max(number, 0), color)
        for label, key, color in definitions
        if (number := _number(raw.get(key))) is not None
    ]
    if not values:
        return ""
    maximum = max(max(value for _, value, _ in values), 1)
    row_height = 34
    height = 26 + len(values) * row_height
    rows = []
    for index, (label, value, color) in enumerate(values):
        y = 18 + index * row_height
        width = max(value / maximum * 350, 3 if value > 0 else 0)
        rows.append(f"""
          <text x="0" y="{y + 14}" fill="{_TEXT}" font-size="13">{_esc(label)}</text>
          <rect x="58" y="{y}" width="350" height="20" rx="5" fill="#f1f5f9"/>
          <rect x="58" y="{y}" width="{width:.2f}" height="20" rx="5" fill="{color}" opacity="0.9"/>
          <text x="422" y="{y + 14}" fill="#0f172a" font-size="13" font-weight="700">{value:,.0f} 家</text>
        """)
    svg = f'<svg data-testid="daily-review-breadth-chart" viewBox="0 0 560 {height}" role="img" aria-label="市场涨跌分布图">{"".join(rows)}</svg>'
    return svg


def _render_index_chart(snapshot: DailyReviewDataSnapshot) -> str:
    values = _named_values(snapshot.indices, 6)
    if not values:
        return ""
    maximum = max(max(abs(value) for _, value in values), 1)
    center = 320
    max_width = 176
    row_height = 34
    height = 24 + len(values) * row_height
    rows = [f'<line x1="{center}" x2="{center}" y1="4" y2="{height - 4}" stroke="{_GRID}"/>']
    for index, (name, value) in enumerate(values):
        y = 14 + index * row_height
        width = max(abs(value) / maximum * max_width, 3 if value else 0)
        x = center if value >= 0 else center - width
        color = _UP if value >= 0 else _DOWN
        rows.append(f"""
          <text x="0" y="{y + 14}" fill="{_TEXT}" font-size="13">{_esc(_trim_label(name))}</text>
          <rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="20" rx="4" fill="{color}" opacity="0.9"/>
          <text x="548" y="{y + 14}" text-anchor="end" fill="{color}" font-size="13" font-weight="700">{_esc(_format_percent(value))}</text>
        """)
    svg = f'<svg data-testid="daily-review-index-chart" viewBox="0 0 560 {height}" role="img" aria-label="核心指数涨跌幅图">{"".join(rows)}</svg>'
    return svg


def _render_sector_chart(snapshot: DailyReviewDataSnapshot) -> str:
    values = [
        *((name, value, True) for name, value in _named_values(snapshot.top_sectors, 5)),
        *((name, value, False) for name, value in _named_values(snapshot.bottom_sectors, 5)),
    ]
    if not values:
        return ""
    maximum = max(max(abs(value) for _, value, _ in values), 1)
    center = 310
    max_width = 184
    row_height = 31
    height = 32 + len(values) * row_height
    rows = [f'<line x1="{center}" x2="{center}" y1="4" y2="{height - 4}" stroke="{_GRID}"/>']
    for index, (name, value, strong) in enumerate(values):
        y = 18 + index * row_height
        width = max(abs(value) / maximum * max_width, 3 if value else 0)
        x = center if strong else center - width
        color = _UP if strong else _DOWN
        rows.append(f"""
          <text x="0" y="{y + 13}" fill="{_TEXT}" font-size="12">{_esc(_trim_label(name))}</text>
          <rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="18" rx="4" fill="{color}" opacity="0.9"/>
          <text x="548" y="{y + 13}" text-anchor="end" fill="{color}" font-size="12" font-weight="700">{_esc(_format_percent(value))}</text>
        """)
    svg = f'<svg data-testid="daily-review-sector-chart" viewBox="0 0 560 {height}" role="img" aria-label="板块强弱对比图">{"".join(rows)}</svg>'
    return svg


def _render_volume_chart(snapshot: DailyReviewDataSnapshot) -> str:
    raw = snapshot.market_volume
    definitions = (
        ("当日成交额", "amount", _PRIMARY),
        ("前一日成交额", "amount_before_one_day", "#7c3aed"),
        ("20 日均值", "amount_average_20_day", "#f59e0b"),
        ("60 日均值", "amount_average_60_day", "#0891b2"),
    )
    values = [
        (label, max(number, 0), color)
        for label, key, color in definitions
        if (number := _number(raw.get(key))) is not None
    ]
    if not values:
        return ""
    maximum = max(max(value for _, value, _ in values), 1)
    rows = []
    count = len(values)
    slot = 560.0 / count
    width = min(84.0, slot * 0.65)
    for index, (label, value, color) in enumerate(values):
        x = index * slot + (slot - width) / 2.0
        bar_height = value / maximum * 82.0
        rows.append(f"""
          <text x="{x + width / 2.0:.1f}" y="{116 - bar_height:.1f}" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="700">{_esc(_format_amount(value))}</text>
          <rect x="{x:.1f}" y="{122 - bar_height:.1f}" width="{width:.1f}" height="{bar_height:.1f}" rx="6" fill="{color}" opacity="0.9"/>
          <text x="{x + width / 2.0:.1f}" y="146" text-anchor="middle" fill="{_TEXT}" font-size="12">{_esc(label)}</text>
        """)
    svg = f'<svg data-testid="daily-review-volume-chart" viewBox="0 0 560 158" role="img" aria-label="市场成交额对比图">{"".join(rows)}</svg>'
    return svg


def daily_review_chart_svgs(snapshot: DailyReviewDataSnapshot) -> list[tuple[str, str, str]]:
    """返回复盘图表的 (标题, 副标题, SVG) 列表，供 PDF 渲染与推送图片共用；无数据的图表自动略去。"""
    charts = (
        ("市场涨跌分布", "上涨 / 下跌家数与涨跌停情绪", _render_breadth_chart(snapshot)),
        ("核心指数表现", "主要指数当日涨跌幅", _render_index_chart(snapshot)),
        ("板块强弱对比", "领涨与领跌板块双向对照", _render_sector_chart(snapshot)),
        ("市场成交额", "当日、前一日、20 日与 60 日均值", _render_volume_chart(snapshot)),
    )
    return [(title, subtitle, svg) for title, subtitle, svg in charts if svg]


def _render_charts(snapshot: DailyReviewDataSnapshot) -> str:
    cards = "".join(
        _chart_card(title, subtitle, svg)
        for title, subtitle, svg in daily_review_chart_svgs(snapshot)
    )
    if not cards:
        return '<div class="empty-state">暂无可视化数据</div>'
    return f'<div class="chart-grid">{cards}</div>'


def _render_list(values: Iterable[str], empty: str = "暂无可靠结论") -> str:
    items = [f"<li>{_esc(value)}</li>" for value in values if str(value).strip()]
    return f'<ul>{"".join(items)}</ul>' if items else f'<div class="empty-inline">{_esc(empty)}</div>'


def _render_section(section: DailyReviewSection) -> str:
    return f"""
      <div class="review-block">
        <h3>{_esc(section.title)}</h3>
        <p>{_esc(section.summary) or '暂无摘要'}</p>
        {_render_list(section.bullets, '暂无补充要点')}
      </div>
    """


_EVENT_TYPE_LABELS = {
    "policy": "政策",
    "macro": "宏观",
    "global": "海外",
    "industry": "产业",
    "market": "市场",
}
_DIRECTION_LABELS = {
    "positive": "偏利好",
    "negative": "偏利空",
    "mixed": "影响分化",
    "neutral": "方向待确认",
}
_TIMING_LABELS = {
    "before": "盘前/事前",
    "on_date": "复盘日",
    "after": "事后验证",
}
_HORIZON_LABELS = {
    "intraday": "日内",
    "short_term": "短期",
    "medium_term": "中期",
}


def _impact_row(label: str, value: str, *, class_name: str = "") -> str:
    classes = f"impact-row {class_name}".strip()
    return (
        f'<div class="{classes}"><div class="impact-label">{_esc(label)}</div>'
        f'<div class="impact-value">{_esc(value) or "-"}</div></div>'
    )


def _render_policy_summary(section: DailyReviewSection) -> str:
    return f"""
      <div class="policy-summary-copy">
        <p>{_esc(section.summary) or '暂无摘要'}</p>
        {_render_list(section.bullets, '暂无补充要点')}
      </div>
    """


def _render_event_impact(impact: DailyReviewEventImpact, index: int) -> str:
    sectors = "、".join(impact.affected_sectors) or "市场整体"
    confirmation = "；".join(impact.confirmation_signals) or "待观察"
    invalidation = "；".join(impact.invalidation_conditions) or "待观察"
    timing_class = " is-after" if impact.timing == "after" else ""
    return f"""
      <article class="policy-impact-card{timing_class}">
        <div class="impact-header">
          <span class="impact-index">{index:02d}</span>
          <div class="impact-title">{_esc(impact.event_title)}</div>
          <div class="impact-tags">
            <span>{_esc(_EVENT_TYPE_LABELS.get(impact.event_type, impact.event_type))}</span>
            <span>{_esc(_DIRECTION_LABELS.get(impact.direction, impact.direction))}</span>
            <span>{_esc(_HORIZON_LABELS.get(impact.horizon, impact.horizon))}</span>
            <span>{_esc(_TIMING_LABELS.get(impact.timing, impact.timing))}</span>
          </div>
        </div>
        <div class="impact-rows">
          {_impact_row("影响方向", sectors)}
          {_impact_row("传导链", impact.transmission_chain)}
          {_impact_row("事实证据", impact.evidence, class_name="is-evidence")}
          {_impact_row("盘面验证", impact.market_confirmation or "尚未核验", class_name="is-confirmation")}
          {_impact_row("确认信号", confirmation)}
          {_impact_row("失效条件", invalidation, class_name="is-risk")}
        </div>
      </article>
    """


def _render_safe_markdown(value: str) -> str:
    """渲染常用标题、列表和段落；所有文本先转义，不执行任意 HTML。"""
    text = str(value or "").replace("\\n", "\n").strip()
    if not text:
        return ""
    output: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f'<p>{"<br>".join(_esc(line) for line in paragraph)}</p>')
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            output.append(f'<ul>{"".join(f"<li>{_esc(item)}</li>" for item in list_items)}</ul>')
            list_items.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        bullet = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = min(len(heading.group(1)) + 2, 5)
            output.append(f"<h{level}>{_esc(heading.group(2))}</h{level}>")
        elif bullet:
            flush_paragraph()
            list_items.append(bullet.group(1))
        else:
            flush_list()
            paragraph.append(line)
    flush_paragraph()
    flush_list()
    return "".join(output)


def generate_daily_review_pdf_html(result: DailyReviewResult) -> str:
    """生成包含复盘正文与四类市场图表的 A4 HTML。"""
    state_labels = {"attack": "进攻", "balanced": "均衡", "defensive": "防守", "unknown": "数据不足"}
    quality_label = "完整" if result.quality_status == "complete" else "降级"
    generation_label = "AI 生成" if result.generation_status == "llm" else "确定性兜底"
    # PDF 使用结构化字段独立排版，避免 Markdown 的二级列表被压平成同一层，
    # 导致“新闻政策与影响传导”的标签和值错位。llm_review 仍用于页面正文和复制导出。
    core_sections_html = "".join(_render_section(section) for section in (
        result.index_review,
        result.hotspot_review,
        result.dragon_tiger_review,
    ))
    policy_section_html = _render_policy_summary(result.news_policy_review)
    policy_impacts = list(result.event_impacts)
    first_policy_impact = _render_event_impact(policy_impacts[0], 1) if policy_impacts else ""
    remaining_policy_impacts = "".join(
        _render_event_impact(impact, index)
        for index, impact in enumerate(policy_impacts[1:], start=2)
    )
    empty_policy_impacts = '<div class="empty-state">暂无可核验的重点政策事件</div>' if not policy_impacts else ""
    warnings = [*result.warnings, *result.source_errors.values()]
    invalid = [f"失效条件：{item}" for item in result.invalid_conditions]

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{_esc(result.title)}</title>
<style>
  @page {{ size: A4; margin: 16mm 14mm 18mm; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; color: #0f172a; background: #fff; font-family: "PingFang SC", "Microsoft YaHei", Arial, sans-serif; font-size: 11px; line-height: 1.65; overflow-wrap: anywhere; }}
  h1, h2, h3, h4, h5 {{ margin: 0; break-after: avoid; }}
  h1 {{ color: #0f3b82; font-size: 24px; line-height: 1.35; }}
  h2 {{ margin-bottom: 12px; padding-bottom: 6px; color: #0f4cbd; border-bottom: 2px solid #dbeafe; font-size: 16px; }}
  h3 {{ margin: 12px 0 5px; color: #1e3a5f; font-size: 13px; }}
  h4, h5 {{ margin: 10px 0 4px; color: #334155; font-size: 12px; }}
  p {{ margin: 4px 0 8px; white-space: normal; }}
  ul {{ margin: 5px 0 8px; padding-left: 18px; }}
  li {{ margin: 3px 0; }}
  .hero {{ padding: 22px 24px; color: #fff; border-radius: 10px; background: linear-gradient(135deg, #0f3b82, #2563eb); }}
  .hero h1, .hero .summary {{ color: #fff; }}
  .hero .summary {{ margin: 10px 0 12px; font-size: 12px; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 7px; }}
  .pill {{ padding: 3px 8px; border: 1px solid rgba(255,255,255,.35); border-radius: 999px; background: rgba(255,255,255,.13); }}
  .section {{ margin-top: 14px; padding: 14px 16px; border: 1px solid #e2e8f0; border-radius: 9px; break-inside: avoid; }}
  .section.allow-break {{ break-inside: auto; }}
  .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .chart-card {{ min-width: 0; padding: 10px; border: 1px solid #dbe3ef; border-radius: 7px; break-inside: avoid; }}
  .chart-heading {{ display: flex; flex-direction: column; margin-bottom: 5px; }}
  .chart-heading strong {{ font-size: 12px; }}
  .chart-heading span {{ color: #64748b; font-size: 9px; }}
  .chart-card svg {{ display: block; width: 100%; height: auto; }}
  .review-block {{ margin-bottom: 12px; break-inside: avoid; }}
  .review-block:last-child {{ margin-bottom: 0; }}
  .policy-opening {{ break-inside: avoid; page-break-inside: avoid; }}
  .policy-summary {{ margin-bottom: 10px; padding: 9px 12px; border-radius: 7px; background: #f8fafc; }}
  .policy-summary-copy p {{ margin-top: 0; }}
  .policy-summary-copy ul {{ margin-bottom: 0; }}
  .policy-impact-card {{ width: 100%; margin: 0 0 8px; border: 1px solid #dbe3ef; border-left: 4px solid #2563eb; border-radius: 8px; background: #fff; break-inside: avoid; page-break-inside: avoid; overflow: hidden; }}
  .policy-impact-card.is-after {{ border-left-color: #d97706; }}
  .impact-header {{ display: grid; grid-template-columns: 28px minmax(0, 1fr); column-gap: 8px; row-gap: 5px; align-items: start; padding: 8px 10px 7px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }}
  .impact-index {{ display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 22px; color: #fff; border-radius: 5px; background: #2563eb; font-size: 9px; font-weight: 700; line-height: 22px; text-align: center; }}
  .is-after .impact-index {{ background: #d97706; }}
  .impact-title {{ min-width: 0; color: #172554; font-size: 12px; font-weight: 700; line-height: 1.5; overflow-wrap: anywhere; }}
  .impact-tags {{ grid-column: 2; display: flex; flex-wrap: wrap; gap: 4px; min-width: 0; }}
  .impact-tags span {{ display: inline-block; padding: 1px 6px; color: #334155; border: 1px solid #cbd5e1; border-radius: 999px; background: #fff; font-size: 8px; line-height: 1.5; white-space: nowrap; }}
  .impact-rows {{ padding: 3px 10px 6px; }}
  .impact-row {{ display: grid; grid-template-columns: 64px minmax(0, 1fr); column-gap: 10px; align-items: start; padding: 5px 0; border-bottom: 1px solid #eef2f7; }}
  .impact-row:last-child {{ border-bottom: 0; }}
  .impact-label {{ color: #64748b; font-size: 9px; font-weight: 700; line-height: 1.65; text-align: right; white-space: nowrap; }}
  .impact-value {{ min-width: 0; color: #1e293b; font-size: 9.5px; line-height: 1.55; overflow-wrap: anywhere; word-break: break-word; }}
  .impact-row.is-evidence .impact-value {{ color: #475569; font-size: 8.5px; }}
  .impact-row.is-confirmation .impact-value {{ color: #0f4c81; }}
  .impact-row.is-risk .impact-value {{ color: #9a3412; }}
  .callout-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; }}
  .callout {{ min-width: 0; padding: 10px; border-radius: 7px; border-left: 3px solid; background: #f8fafc; break-inside: avoid; }}
  .callout.opportunity {{ border-color: {_UP}; background: #fff7f7; }}
  .callout.risk {{ border-color: #d97706; background: #fffbeb; }}
  .callout.strategy {{ border-color: {_PRIMARY}; background: #eff6ff; }}
  .callout strong {{ display: block; margin-bottom: 4px; }}
  .empty-state {{ padding: 26px; color: #94a3b8; text-align: center; border: 1px dashed #cbd5e1; border-radius: 7px; background: #f8fafc; }}
  .empty-inline {{ color: #94a3b8; }}
  .notice {{ color: #475569; background: #f8fafc; }}
  .footer-note {{ margin-top: 16px; color: #64748b; text-align: center; font-size: 9px; }}
</style>
</head>
<body>
  <header class="hero">
    <h1>{_esc(result.title)}</h1>
    <div class="summary">{_esc(result.market_summary) or '核心数据不足，无法形成完整市场结论。'}</div>
    <div class="meta">
      <span class="pill">交易日：{_esc(result.effective_date or result.date)}</span>
      <span class="pill">市场状态：{_esc(state_labels.get(result.market_state, '数据不足'))}</span>
      <span class="pill">建议仓位：{_esc(result.position_range or '待定')}</span>
      <span class="pill">质量：{quality_label}</span>
      <span class="pill">报告：{generation_label}</span>
    </div>
  </header>

  <section class="section allow-break">
    <h2>01 · 市场数据图谱</h2>
    {_render_charts(result.data_snapshot)}
  </section>

  <section class="section allow-break">
    <h2>02 · 每日复盘正文</h2>
    {core_sections_html}
  </section>

  <section class="section allow-break policy-section">
    <div class="policy-opening">
      <h2>03 · 新闻政策与影响传导</h2>
      <div class="policy-summary">{policy_section_html}</div>
      {first_policy_impact}
      {empty_policy_impacts}
    </div>
    {remaining_policy_impacts}
  </section>

  <section class="section allow-break">
    <h2>04 · 机会、风险与明日策略</h2>
    <div class="callout-grid">
      <div class="callout opportunity"><strong>机会方向</strong>{_render_list(result.opportunities)}</div>
      <div class="callout risk"><strong>风险提示</strong>{_render_list(result.risk_alerts)}</div>
      <div class="callout strategy"><strong>明日交易计划</strong>{_render_list([*result.strategy_notes, *invalid])}</div>
    </div>
  </section>

  <section class="section notice">
    <h2>05 · 数据覆盖与缺口</h2>
    {_render_list([*result.data_gaps, *warnings], '核心数据维度未发现明确缺口')}
  </section>

  <div class="footer-note">生成时间：{_esc(result.generated_at)} · 以上内容仅供研究参考，不构成投资建议。</div>
</body>
</html>"""


async def render_daily_review_pdf_bytes(html_content: str) -> bytes:
    """通过共享的有界 Chromium 队列渲染报告，保留既有页眉页脚和 A4 布局。"""
    return await render_pdf(
        html_content,
        header_template='<div style="font-size:8px;width:100%;text-align:right;color:#94a3b8;padding-right:14mm;font-family:sans-serif;">A股智能投研体系 · 每日复盘报告</div>',
        footer_template='<div style="font-size:8px;width:100%;display:flex;justify-content:space-between;color:#94a3b8;padding:0 14mm;font-family:sans-serif;"><span>内部研究参考 · 不构成投资建议</span><span>第 <span class="pageNumber"></span> 页 / 共 <span class="totalPages"></span> 页</span></div>',
    )
