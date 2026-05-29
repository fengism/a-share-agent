from app.models.analysis import AnalysisResult, FactorAnalysis
from app.models.daily_review import DailyReviewResult, DailyReviewSection

_MAX_TEXT_LENGTH = 1800


def _text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text or "-"


def _chunks(value: object) -> list[str]:
    text = _text(value)
    return [text[index:index + _MAX_TEXT_LENGTH] for index in range(0, len(text), _MAX_TEXT_LENGTH)] or ["-"]


def _rich_text(value: object) -> list[dict]:
    return [{"type": "text", "text": {"content": chunk}} for chunk in _chunks(value)]


def _heading(text: str, level: int = 2) -> dict:
    block_type = f"heading_{level}"
    return {"object": "block", "type": block_type, block_type: {"rich_text": _rich_text(text)}}


def _paragraph(text: object) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(text)}}


def _bullet(text: object) -> dict:
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rich_text(text)}}


def _section_blocks(section: DailyReviewSection) -> list[dict]:
    blocks = [_heading(section.title, level=3), _paragraph(section.summary)]
    blocks.extend(_bullet(item) for item in section.bullets)
    return blocks


def _factor_blocks(title: str, factor: FactorAnalysis) -> list[dict]:
    blocks = [_heading(f"{title}：{factor.score}/10", level=3), _paragraph(factor.summary)]
    if factor.strengths:
        blocks.append(_paragraph("优势"))
        blocks.extend(_bullet(item) for item in factor.strengths)
    if factor.risks:
        blocks.append(_paragraph("风险"))
        blocks.extend(_bullet(item) for item in factor.risks)
    return blocks


def format_daily_review(review: DailyReviewResult) -> tuple[str, list[dict]]:
    title = f"每日复盘 - {review.date}"
    blocks: list[dict] = [
        _heading("市场摘要"),
        _paragraph(review.market_summary),
        _paragraph(f"生成时间：{review.generated_at}"),
    ]
    if review.llm_review.strip():
        blocks.extend([_heading("AI 复盘报告"), _paragraph(review.llm_review)])
    else:
        blocks.extend(_section_blocks(review.index_review))
        blocks.extend(_section_blocks(review.hotspot_review))
        blocks.extend(_section_blocks(review.dragon_tiger_review))
    blocks.append(_heading("机会"))
    blocks.extend(_bullet(item) for item in (review.opportunities or ["-"]))
    blocks.append(_heading("风险"))
    blocks.extend(_bullet(item) for item in (review.risk_alerts or ["-"]))
    blocks.append(_heading("策略"))
    blocks.extend(_bullet(item) for item in (review.strategy_notes or ["-"]))
    blocks.extend([
        _heading("原始数据摘要"),
        _paragraph(f"指数样本：{len(review.data_snapshot.indices)}；热点股：{len(review.data_snapshot.hot_stocks)}；龙虎榜：{len(review.data_snapshot.dragon_tiger)}"),
    ])
    return title, blocks


def format_analysis_result(result: AnalysisResult) -> tuple[str, list[dict]]:
    title = f"股票分析 - {result.stock_code} - {result.stock_name} - {result.analysis_date}"
    price_low, price_high = result.estimated_price_range
    blocks: list[dict] = [
        _heading("综合结论"),
        _paragraph(f"当前价格：{result.current_price}；综合评分：{result.overall_rating}/10；信号：{result.signal}；置信度：{result.confidence:.0%}"),
        _paragraph(f"目标价格区间：{price_low} - {price_high}"),
        _paragraph(result.overall_summary),
    ]
    blocks.extend(_factor_blocks("基本面", result.fundamental))
    blocks.extend(_factor_blocks("技术面", result.technical))
    blocks.extend(_factor_blocks("情绪面", result.sentiment))
    blocks.append(_heading("关键因素"))
    blocks.extend(_bullet(item) for item in (result.key_factors or ["-"]))
    blocks.append(_heading("风险提示"))
    blocks.extend(_bullet(item) for item in (result.risk_warnings or ["-"]))
    return title, blocks
