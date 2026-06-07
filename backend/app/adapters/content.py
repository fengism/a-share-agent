from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Union

from app.models.analysis import AnalysisResult, FactorAnalysis
from app.models.daily_review import DailyReviewResult, DailyReviewSection


@dataclass
class ContentBlock:
    """Purpose: 统一内容块结构，表示飞书/Notion 等平台共用的文档片段单元。"""
    type: Literal["heading", "paragraph", "bullet", "divider"]
    level: int = 0
    text: str = ""


def _strip_markdown(text: str) -> str:
    """去除 markdown 粗体/斜体标记，保留纯文本。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _parse_markdown_blocks(text: str) -> list[ContentBlock]:
    """将 markdown 文本解析为 ContentBlock 列表，适配飞书文档呈现。"""
    blocks: list[ContentBlock] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            level = min(level, 3)
            blocks.append(ContentBlock(type="heading", level=level, text=_strip_markdown(heading_match.group(2))))
        elif stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("+ "):
            blocks.append(ContentBlock(type="bullet", text=_strip_markdown(stripped[2:])))
        elif re.match(r"^\d+[.)]\s+", stripped):
            content = re.sub(r"^\d+[.)]\s+", "", stripped)
            blocks.append(ContentBlock(type="bullet", text=_strip_markdown(content)))
        else:
            blocks.append(ContentBlock(type="paragraph", text=_strip_markdown(stripped)))
    return blocks


def build_content(data_type: str, data) -> list[ContentBlock]:
    """根据数据类型分发到对应的内容构建函数。

    Param:
        data_type: 数据类型标识，支持 "daily_review"、"analysis"、"chat"
        data: 对应类型的模型实例或原始文本
    Return:
        ContentBlock 列表，供飞书/Notion 适配器使用
    """
    if data_type == "daily_review":
        return _build_daily_review(data)
    if data_type == "analysis":
        return _build_analysis(data)
    if data_type == "chat":
        return _build_chat(data)
    if data_type == "industry_chain":
        return _build_industry_chain(data)
    raise ValueError(f"Unknown data_type: {data_type}")


def _build_chat(markdown_text: str) -> list[ContentBlock]:
    """将聊天消息的 markdown 文本解析为 ContentBlock 列表。

    Param:
        markdown_text: 含 markdown 标记的聊天内容
    Return:
        解析后的 ContentBlock 列表
    """
    return _parse_markdown_blocks(markdown_text)


def _build_daily_review(review: DailyReviewResult) -> list[ContentBlock]:
    """将每日复盘结果组装为 ContentBlock 列表。

    Param:
        review: 每日复盘结果模型
    Return:
        按章节顺序排列的 ContentBlock 列表
    """
    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=2, text="市场摘要"),
        ContentBlock(type="paragraph", text=review.market_summary),
        ContentBlock(type="paragraph", text=f"生成时间：{review.generated_at}"),
    ]
    if review.llm_review.strip():
        blocks.append(ContentBlock(type="heading", level=2, text="AI 复盘报告"))
        blocks.extend(_parse_markdown_blocks(review.llm_review))
    else:
        blocks.extend(_section_blocks(review.index_review))
        blocks.extend(_section_blocks(review.hotspot_review))
        blocks.extend(_section_blocks(review.dragon_tiger_review))
    blocks.append(ContentBlock(type="heading", level=2, text="机会"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.opportunities or ["-"]))
    blocks.append(ContentBlock(type="heading", level=2, text="风险"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.risk_alerts or ["-"]))
    blocks.append(ContentBlock(type="heading", level=2, text="策略"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (review.strategy_notes or ["-"]))
    blocks.append(ContentBlock(type="heading", level=2, text="原始数据摘要"))
    blocks.append(ContentBlock(type="paragraph", text=f"指数样本：{len(review.data_snapshot.indices)}；热点股：{len(review.data_snapshot.hot_stocks)}；龙虎榜：{len(review.data_snapshot.dragon_tiger)}"))
    return blocks


def _section_blocks(section: DailyReviewSection) -> list[ContentBlock]:
    """将每日复盘的单个章节渲染为 ContentBlock 列表。

    Param:
        section: 复盘章节模型，包含标题、摘要和要点列表
    Return:
        包含标题、摘要和要点的 ContentBlock 列表
    """
    blocks = [
        ContentBlock(type="heading", level=3, text=section.title),
        ContentBlock(type="paragraph", text=section.summary),
    ]
    blocks.extend(ContentBlock(type="bullet", text=item) for item in section.bullets)
    return blocks


def _build_analysis(result: AnalysisResult) -> list[ContentBlock]:
    """将个股分析结果组装为 ContentBlock 列表。

    Param:
        result: 个股分析结果模型
    Return:
        包含综合结论、各维度分析、关键因素和风险提示的 ContentBlock 列表
    """
    price_low, price_high = result.estimated_price_range
    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=2, text="综合结论"),
        ContentBlock(type="paragraph", text=f"当前价格：{result.current_price}；综合评分：{result.overall_rating}/10；信号：{result.signal}；置信度：{result.confidence:.0%}"),
        ContentBlock(type="paragraph", text=f"目标价格区间：{price_low} - {price_high}"),
        ContentBlock(type="paragraph", text=result.overall_summary),
    ]
    blocks.extend(_factor_blocks("基本面", result.fundamental))
    blocks.extend(_factor_blocks("技术面", result.technical))
    blocks.extend(_factor_blocks("情绪面", result.sentiment))
    blocks.append(ContentBlock(type="heading", level=2, text="关键因素"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (result.key_factors or ["-"]))
    blocks.append(ContentBlock(type="heading", level=2, text="风险提示"))
    blocks.extend(ContentBlock(type="bullet", text=item) for item in (result.risk_warnings or ["-"]))
    return blocks


def _build_industry_chain(result) -> list[ContentBlock]:
    """将产业链分析结果渲染为 ContentBlock 列表。

    Param:
        result: IndustryChainResult 对象或含相同字段的 dict
    Return:
        ContentBlock 列表
    """
    def _get(key, default=""):
        if isinstance(result, dict):
            return result.get(key, default)
        return getattr(result, key, default)

    blocks: list[ContentBlock] = [
        ContentBlock(type="heading", level=2, text=f"{_get('name', '产业链')} 产业链分析"),
    ]
    summary = _get("summary", "").strip()
    if summary:
        blocks.append(ContentBlock(type="paragraph", text=summary))

    for stage_key, stage_title in (
        ("upstream", "上游"),
        ("midstream", "中游"),
        ("downstream", "下游"),
    ):
        items = _get(stage_key, []) or []
        if items:
            blocks.append(ContentBlock(type="heading", level=3, text=stage_title))
            for item in items:
                if isinstance(item, dict):
                    text = str(item.get("name") or item.get("code") or item)
                else:
                    text = str(item)
                blocks.append(ContentBlock(type="bullet", text=text))

    drivers = _get("drivers", []) or []
    if drivers:
        blocks.append(ContentBlock(type="heading", level=3, text="驱动因素"))
        blocks.extend(ContentBlock(type="bullet", text=str(d)) for d in drivers)

    risks = _get("risks", []) or []
    if risks:
        blocks.append(ContentBlock(type="heading", level=3, text="风险提示"))
        blocks.extend(ContentBlock(type="bullet", text=str(r)) for r in risks)

    key_stocks = _get("key_stocks", []) or []
    if key_stocks:
        blocks.append(ContentBlock(type="heading", level=3, text="重点关注"))
        for stock in key_stocks:
            if isinstance(stock, dict):
                text = str(stock.get("name") or stock.get("code") or stock)
            else:
                text = str(stock)
            blocks.append(ContentBlock(type="bullet", text=text))

    llm_review = _get("llm_review", "").strip()
    if llm_review:
        blocks.append(ContentBlock(type="heading", level=2, text="AI 复盘报告"))
        blocks.extend(_parse_markdown_blocks(llm_review))

    return blocks


def _factor_blocks(title: str, factor: FactorAnalysis) -> list[ContentBlock]:
    """将单维度因子分析渲染为 ContentBlock 列表。

    Param:
        title: 维度名称，如"基本面"
        factor: 因子分析模型
    Return:
        包含标题、摘要、优势和风险的 ContentBlock 列表
    """
    blocks = [
        ContentBlock(type="heading", level=3, text=f"{title}：{factor.score}/10"),
        ContentBlock(type="paragraph", text=factor.summary),
    ]
    if factor.strengths:
        blocks.append(ContentBlock(type="paragraph", text="优势"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in factor.strengths)
    if factor.risks:
        blocks.append(ContentBlock(type="paragraph", text="风险"))
        blocks.extend(ContentBlock(type="bullet", text=item) for item in factor.risks)
    return blocks
