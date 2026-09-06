from __future__ import annotations

import json
import math
from typing import Any

from app.agentic.public import (
    AgentEventCallback,
    AgenticResearchResult,
    AgentResearchSpec,
    EvidenceRequirement,
    run_agentic_research,
)


def _decoded_content(evidence) -> Any:
    try:
        value = json.loads(evidence.content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return evidence.content
    if isinstance(value, dict) and value.get("ok") is True and "data" in value:
        return value["data"]
    return value


def _flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return "\n".join(_flatten_text(item) for item in value)
    return str(value) if value is not None else ""


def _body_records(value: Any) -> list[tuple[str, str]]:
    if isinstance(value, list):
        return [record for item in value for record in _body_records(item)]
    if not isinstance(value, dict):
        return []
    content = value.get("content")
    url = str(value.get("url") or "")
    records = [(url, content)] if isinstance(content, str) else []
    for key, item in value.items():
        if key not in {"content", "url"}:
            records.extend(_body_records(item))
    return records


def _has_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, dict):
        return any(_has_finite_number(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_finite_number(item) for item in value)
    return False


def _has_financial_evidence(evidence) -> bool:
    payload = _decoded_content(evidence)
    if not isinstance(payload, dict):
        return False
    return any(
        _has_finite_number(payload.get(key))
        for key in ("income", "balance", "cashflow", "key_indicators", "income_raw")
    )


def _has_web_body(evidence) -> bool:
    return any(
        url.startswith(("http://", "https://")) and len(content.strip()) >= 300
        for url, content in _body_records(_decoded_content(evidence))
    )


def _has_structured_research_evidence(evidence) -> bool:
    payload = _decoded_content(evidence)
    records = payload if isinstance(payload, list) else payload.get("items", []) if isinstance(payload, dict) else []
    return isinstance(records, list) and bool(records) and len(_flatten_text(records).strip()) >= 120


def _research_evidence_contains(evidence, keywords: tuple[str, ...]) -> bool:
    text = _flatten_text(_decoded_content(evidence)).strip()
    return len(text) >= 120 and any(keyword in text for keyword in keywords)


def _has_industry_research_evidence(evidence) -> bool:
    if evidence.tool_name in {"fetch_url", "fetch_urls"} and not _has_web_body(evidence):
        return False
    if evidence.tool_name == "iwencai_query" and not _has_structured_research_evidence(evidence):
        return False
    return _research_evidence_contains(evidence, ("行业", "市场", "竞争", "产业链", "上游", "下游", "份额"))


def _has_management_research_evidence(evidence) -> bool:
    if evidence.tool_name in {"fetch_url", "fetch_urls"} and not _has_web_body(evidence):
        return False
    if evidence.tool_name == "iwencai_query" and not _has_structured_research_evidence(evidence):
        return False
    return _research_evidence_contains(evidence, ("管理层", "董事", "高管", "股东", "分红", "回购", "并购", "研发"))


def _has_moat_research_evidence(evidence) -> bool:
    if evidence.tool_name in {"fetch_url", "fetch_urls"} and not _has_web_body(evidence):
        return False
    if evidence.tool_name == "iwencai_query" and not _has_structured_research_evidence(evidence):
        return False
    return _research_evidence_contains(
        evidence,
        ("品牌", "定价", "客户", "渠道", "成本", "规模", "技术", "专利", "竞争优势"),
    )


ANALYSIS_RESEARCH_SPEC = AgentResearchSpec(
    name="stock-analysis-research",
    display_name="个股动态调研",
    system_prompt="""你是严谨的 A 股研究 Agent。你的任务是围绕指定股票和分析日期自主规划调研，并通过工具获取可验证证据。

要求：
- 财务数据权威性：官方财务与结构化接口（analyze_financials, get_stock_info, get_stock_valuation_detail 等）返回的数据具有最高事实优先级。如果搜索（web_search）或抓取（fetch_url）中的二手财务数据与财报接口返回的数据存在差异或冲突，必须无条件以财报接口数据为准，严禁采用 search 摘要覆盖财报接口。
- 自主决定工具调用顺序，可多轮调用并根据结果补充调查。
- 覆盖基础资料、估值、财务、长期公开研究、技术择时、新闻情绪、风险和市场环境。
- 长期研究需调查盈利引擎与分部质量、护城河及反证、管理层与资本配置、行业与价值链、失败路径和估值假设。
- 使用搜索工具发现公告、公司披露、交易所资料和权威行业材料后，优先调用 fetch_url 或 fetch_urls 阅读正文；若链接或资料为 PDF 研报/公告，调用 read_pdf 提取结构化文本与数据表格；搜索摘要不能替代正文证据。
- 保留来源、发布日期、报告期和统计口径；财务与技术判断必须基于工具返回的具体数据。
- 分析营收与毛利构成时关注产品、业务和地区集中度；上游未提供报告期时不得推断日期，各维度不可直接相加。
- 技术面和情绪面仅作为短期择时信息，不用于替代长期商业质量和投资确定性判断。
- 对冲突信息指出口径差异，不得使用常识补写工具未返回的事实；资料不足时明确待核验问题。
- 最终摘要区分事实、推断与数据缺口，并同时给出支持证据、反证和最重要的多空逻辑。""",
    tool_names=(
        "get_stock_info",
        "get_stock_valuation_detail",
        "analyze_financials",
        "get_stock_technical_indicators",
        "get_stock_kline",
        "get_stock_news",
        "get_stock_sentiment",
        "get_stock_risk_data",
        "get_market_overview",
        "iwencai_query",
        "iwencai_search",
        "web_search",
        "fetch_url",
        "fetch_urls",
        "read_pdf",
    ),
    requirements=(
        EvidenceRequirement("profile", "基础信息与盈利引擎", ("get_stock_info",)),
        EvidenceRequirement(
            "valuation",
            "估值",
            ("get_stock_valuation_detail",),
        ),
        EvidenceRequirement(
            "fundamental",
            "财务与分部质量",
            ("analyze_financials",),
            validator=_has_financial_evidence,
        ),
        EvidenceRequirement(
            "industry_research",
            "行业与价值链公开资料",
            ("iwencai_query", "fetch_url", "fetch_urls", "read_pdf"),
            validator=_has_industry_research_evidence,
            fatal=False,
        ),
        EvidenceRequirement(
            "moat_research",
            "护城河与反证公开资料",
            ("iwencai_query", "fetch_url", "fetch_urls", "read_pdf"),
            validator=_has_moat_research_evidence,
            fatal=False,
        ),
        EvidenceRequirement(
            "management_research",
            "管理层与资本配置公开资料",
            ("iwencai_query", "fetch_url", "fetch_urls", "read_pdf"),
            validator=_has_management_research_evidence,
            fatal=False,
        ),
        EvidenceRequirement(
            "technical",
            "技术择时",
            ("get_stock_technical_indicators", "get_stock_kline"),
        ),
        EvidenceRequirement(
            "sentiment",
            "新闻与情绪择时",
            ("get_stock_news", "get_stock_sentiment"),
        ),
        EvidenceRequirement("risk", "风险与熊市线索", ("get_stock_risk_data",)),
        EvidenceRequirement("market", "市场环境", ("get_market_overview",)),
    ),
)


async def research_stock(
    code: str,
    analysis_date: str,
    settings: Any = None,
    event_callback: AgentEventCallback | None = None,
) -> AgenticResearchResult:
    return await run_agentic_research(
        ANALYSIS_RESEARCH_SPEC,
        f"请动态调研股票 {code}，分析日期为 {analysis_date}。完成全维度证据采集并给出研究摘要。",
        settings=settings,
        event_callback=event_callback,
    )
