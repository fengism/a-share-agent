from __future__ import annotations

import json
import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from app.agentic.events import AgentEvent
from app.agentic.public import (
    AgenticResearchResult,
    AgentResearchSpec,
    EvidenceRequirement,
    run_agentic_research,
)
from app.domain.industry_chain import (
    IndustryChainResearchScope,
    render_industry_chain_scope,
    resolve_industry_chain_scope,
)
from app.modules.industry_chain.budget import research_budget_settings, search_policy_limits
from app.modules.industry_chain.chain_reasoning import (
    TIER_QUESTIONS,
    chain_research_plan,
    has_tier_operating_body,
    tier_search_terms,
)
from app.modules.industry_chain.evidence_content import extract_evidence_content
from app.modules.industry_chain.query_plan import DOCUMENT_SEARCH_RULES, render_discovery_plan
from app.modules.industry_chain.templates import research_guidance

_HTTP_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_A_SHARE_CODE_PATTERN = re.compile(r"(?<!\d)(?:(?:00|30|60|68|43|83|87)\d{4}|920\d{3})(?!\d)")


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


def _count_urls(value: Any) -> int:
    return len(set(_HTTP_URL_PATTERN.findall(_flatten_text(value))))


def _has_market_context(evidence) -> bool:
    text = _flatten_text(_decoded_content(evidence)).strip()
    dimensions = (
        "市场", "产业", "行业", "上游", "中游", "下游",
        "产品", "规模", "竞争", "需求", "出货", "芯片", "算力",
        "空间", "增速", "渗透", "应用", "客户",
    )
    return len(text) >= 50 and sum(dimension in text for dimension in dimensions) >= 1


def _has_company_records(evidence) -> bool:
    text = _flatten_text(_decoded_content(evidence))
    codes = set(_A_SHARE_CODE_PATTERN.findall(text))
    if len(codes) >= 1:
        return True
    return _has_public_company_records(evidence)


def _has_public_company_records(evidence) -> bool:
    value = _decoded_content(evidence)
    records = value if isinstance(value, list) else value.get("items", []) if isinstance(value, dict) else []
    if not isinstance(records, list):
        return False
    name_keys = ("name", "company", "公司", "名称", "股票简称")
    names = {
        str(record.get(key)).strip()
        for record in records
        if isinstance(record, dict)
        for key in name_keys
        if record.get(key)
    }
    return len(names) >= 1


def _has_public_sources(evidence) -> bool:
    return _count_urls(_decoded_content(evidence)) >= 1 or len(_flatten_text(_decoded_content(evidence))) >= 60


BODY_TOOLS = ("web_fetch", "fetch_urls", "read_pdf")


def _has_web_body(evidence) -> bool:
    # Search snippets, metadata, error pages and document directories are not bodies.
    return evidence.tool_name in BODY_TOOLS and any(
        part.source_url and len(re.sub(r"\s+", "", part.text)) >= 80
        for part in extract_evidence_content(_decoded_content(evidence))
    )


def _has_company_financials(evidence) -> bool:
    value = _decoded_content(evidence)
    if evidence.tool_name != "analyze_financials" or not isinstance(value, dict):
        return False
    income = value.get("income") or {}
    return bool(value.get("report_date")) and isinstance(income, dict) and any(
        isinstance(income.get(key), (int, float)) and not isinstance(income[key], bool) and math.isfinite(income[key])
        for key in ("revenue_billion", "net_profit_billion", "gross_margin")
    )


def _has_company_disclosure(evidence) -> bool:
    return _has_web_body(evidence) and _has_dimension_context(
        evidence, ("年度报告", "半年度报告", "年报", "公告", "公司", "收入", "毛利", "订单", "产能", "现金流"),
        minimum_matches=3,
    )


def _has_dimension_context(
    evidence,
    terms: tuple[str, ...],
    *,
    minimum_matches: int = 2,
) -> bool:
    if not _has_web_body(evidence):
        return False
    text = "\n".join(part.text for part in extract_evidence_content(_decoded_content(evidence))).lower()
    return len(text) >= 20 and sum(term.lower() in text for term in terms) >= minimum_matches


def _has_chain_topology(evidence) -> bool:
    return _has_dimension_context(
        evidence,
        ("产业链", "上游", "中游", "下游", "原材料", "制造", "应用"),
        minimum_matches=3,
    )


def _has_competition_context(evidence) -> bool:
    return _has_dimension_context(
        evidence,
        ("竞争", "格局", "份额", "集中度", "龙头", "公司", "厂商"),
    )


def _has_technology_context(evidence) -> bool:
    return _has_dimension_context(
        evidence,
        ("技术", "路线", "工艺", "量产", "产品", "性能", "迭代"),
    )


def _has_event_context(evidence) -> bool:
    return _has_dimension_context(
        evidence,
        ("政策", "事件", "公告", "扩产", "并购", "投资", "资本", "订单"),
    )


def _has_risk_driver_context(evidence) -> bool:
    return _has_dimension_context(
        evidence,
        ("风险", "驱动", "催化", "需求", "约束", "波动", "增长"),
    )


_DISCOVERY_AND_BODY_TOOLS = (
    "iwencai_query",
    "iwencai_select_stock",
    "iwencai_search",
    "web_search",
    "web_fetch",
    "fetch_urls",
    "read_pdf",
)


INDUSTRY_CHAIN_RESEARCH_SPEC = AgentResearchSpec(
    name="industry-chain-research",
    display_name="产业链动态调研",
    allow_incomplete_summary=True,
    document_search_guidance=DOCUMENT_SEARCH_RULES,
    system_prompt="""你是产业链研究 Agent。请围绕指定产业自主拆解研究问题，并通过工具进行多轮公开信息调研。

要求：
- 正文研究提取清单（以下维度不是逐项query，也不要求逐指标搜索）：
  1. 市场规模与容量：全球与中国市场规模、未来复合增速（CAGR）、渗透率及统计口径（如 2024A / 2025E / 2030E）；
  2. 上游核心零部件/原材料：技术壁垒、国产替代率、CR3/CR5 集中度与代表供应商；
  3. 中游生产制造/系统集成：关键工艺、分部毛利率与附加值分配、代表制造厂商；
  4. 下游终端应用/客户场景：核心应用领域、终端客户结构、需求增速与商业化落地节点；
  5. 核心技术路线对比：主流路线 vs 新兴路线的优劣势、成本下降曲线与商业化成熟度；
  6. 重点上市公司与弹性标的：核心受益上市公司，结合 get_stock_info 与 analyze_financials 调取真实营收、毛利与市值指标。
- 使用问财工具查找结构化数据、相关公司、研报和资讯；使用 web_search 发现公开来源后，必须调用 web_fetch / fetch_urls 阅读正文；若为 PDF 格式的券商行业研报、白皮书或上市公司公告，主动调用 read_pdf 提取全文与财务表格。
- 用户未指定时间范围时，研报、新闻、政策、事件和技术动态默认限定最近半年，web_search 使用 time_range=half_year。
- 网页检索默认使用中文关键词并设置 language=zh，优先中文权威来源；英文权威材料仅作补充，最终摘要使用中文。
- 以能覆盖多个相邻研究问题的原始文献为发现单位，先找到少量全景/技术与需求侧资料；从同一文献提取市场、竞争和技术，不按维度逐项搜。
- query使用主题/公司、文献主题与必要年份等少量区分词；地域/时段优先用工具筛选和原文口径核对。既不堆所有细指标，也不用空泛的发展前景代替查证。
- 搜索年份服从本次基准日；原文陈旧/范围不符才重搜，不能机械给每个部件和指标分别加当前年份重复搜索。
- 市场规模等低频年度数据可以使用更早资料，但必须优先最新一期并明确统计日期、区域和口径。
- 网页搜索摘要不能替代正文证据；市场规模、份额、增速和日期必须保留来源与统计口径。
- 对冲突数据说明来源、时期和口径差异，不得编造市场份额、公司代码或事件。
- 对重点A股公司优先调用get_stock_documents定位公告/定期报告，end_date使用本次分析基准日；目录只是线索，必须继续read_pdf/web_fetch读取产品收入、毛利、产销量、订单、产能和客户披露。公告可能不在首页，用next_announcement_page有界翻页，不能把空目录写成无披露。
- analyze_financials已含营收构成；revenue_breakdown缺少报告期时必须读原始报告确认，不继承公司报表日期。
- get_commodity_spot_prices旧名称实际为期货连续/主力合约报价，不是现货、基差或企业采购成本。
- get_customs_trade_data只有全国进出口月度总量；matched_commodity_profiles及投资逻辑是静态线索，不能证明某商品出口数量、价格、目的地或公司订单。
- 先选少量与核心矛盾直接相关的公司，逐家实际调用财务工具、定位公告并阅读经营章节，再扩展公司列表。工具可用不等于已完成取证。
- 对每个核心问题沿“需求数量/价格/结构→供给瓶颈→价格成本→利润分配→公司订单、交付、收入、现金流”展开；寻找反例与失效条件，不重复行业常识。
- 预留预算用于公告正文和反证。必须区分未执行、执行失败、已读材料未披露；未读到正文不能宣称公司未披露。
- 最终摘要区分事实、机构预测、推断和证据缺口。""",
    tool_names=(
        "iwencai_select_stock",
        "iwencai_query",
        "iwencai_search",
        "web_search",
        "web_fetch",
        "fetch_urls",
        "read_pdf",
        "get_stock_documents",
        "get_stock_info",
        "get_stock_valuation_detail",
        "analyze_financials",
        "get_commodity_spot_prices",
        "get_customs_trade_data",
    ),
    requirements=(
        EvidenceRequirement(
            "market_boundary",
            "市场与产业边界",
            _DISCOVERY_AND_BODY_TOOLS,
            validator=_has_market_context,
        ),
        EvidenceRequirement(
            "chain_topology",
            "上中下游产业链结构",
            _DISCOVERY_AND_BODY_TOOLS,
            validator=_has_chain_topology,
            fatal=False,
        ),
        EvidenceRequirement(
            "competition",
            "竞争格局与市场份额",
            ("iwencai_select_stock", "get_stock_info", "analyze_financials", *_DISCOVERY_AND_BODY_TOOLS),
            validator=_has_competition_context,
            fatal=False,
        ),
        EvidenceRequirement(
            "technology",
            "技术路线与量产进展",
            _DISCOVERY_AND_BODY_TOOLS,
            validator=_has_technology_context,
            fatal=False,
        ),
        EvidenceRequirement(
            "events",
            "近期政策与资本事件",
            ("iwencai_search", "web_search", "web_fetch", "fetch_urls", "read_pdf"),
            validator=_has_event_context,
            fatal=False,
        ),
        EvidenceRequirement(
            "risks_drivers",
            "行业驱动与风险",
            _DISCOVERY_AND_BODY_TOOLS,
            validator=_has_risk_driver_context,
            fatal=False,
        ),
        EvidenceRequirement(
            "companies",
            "相关公司",
            ("iwencai_select_stock", "iwencai_query", "iwencai_search", "get_stock_info", "analyze_financials", "web_search", "web_fetch", "fetch_urls"),
            validator=_has_company_records,
        ),
        EvidenceRequirement(
            "public_sources",
            "研报与公开来源",
            ("iwencai_search", "web_search", "read_pdf", "web_fetch", "fetch_urls"),
            validator=_has_public_sources,
        ),
        EvidenceRequirement(
            "company_financials", "重点公司财务数据（含报告期）",
            ("analyze_financials",), validator=_has_company_financials, fatal=False,
        ),
        EvidenceRequirement(
            "company_disclosure", "重点公司经营披露正文",
            ("get_stock_documents", *BODY_TOOLS), validator=_has_company_disclosure, fatal=False,
        ),
        EvidenceRequirement(
            "web_content",
            "网页正文证据",
            BODY_TOOLS,
            validator=_has_web_body,
            fatal=False,
        ),
    ),
)


async def research_industry_chain(
    name: str,
    settings: Any = None,
    event_callback: Callable[[AgentEvent], Awaitable[None]] | None = None,
    *,
    scope: IndustryChainResearchScope | None = None,
    atlas_prior: str = "无",
) -> AgenticResearchResult:
    settings, total_calls = research_budget_settings(settings)
    resolved_scope = resolve_industry_chain_scope(scope)
    scope_text = render_industry_chain_scope(resolved_scope)
    guidance = render_discovery_plan(name, resolved_scope) + "\n" + research_guidance(name)
    spec = replace(INDUSTRY_CHAIN_RESEARCH_SPEC, max_tool_turns=8, **search_policy_limits(total_calls),
        reserved_tool_names=BODY_TOOLS, reserved_tool_calls=min(20, total_calls // 3), requirements=(
        *INDUSTRY_CHAIN_RESEARCH_SPEC.requirements,
        *(EvidenceRequirement(
            f"{tier}_operations", f"{label}经营证据",
            ("web_search", "iwencai_search", *BODY_TOOLS),
            validator=lambda item, terms=tier_search_terms(name, tier): has_tier_operating_body(item, terms), fatal=False,
        ) for tier, (label, _) in TIER_QUESTIONS.items()),
    ))
    guidance += (
        f"\n规划约束：搜索组累计最多{spec.search_total_limit}次，每批连续最多{spec.search_burst_limit}次；"
        "web_search与问财搜索/筛选共享上限，不对同一问题机械地双源重复搜。"
        "先用少量互补问题发现来源，读取正文后再列剩余缺口；不同时扩展所有公司和所有指标。"
        "公司先选覆盖不同环节的2-3家，优先公告经营章节，估值不是产业传导研究的必做项。"
    )
    guidance += f"\n本次产业链主调研工具上限{total_calls}次（不是必须用满）；正文预留{spec.reserved_tool_calls}次。\n" + chain_research_plan(name, atlas_prior)
    if resolved_scope.company_scope == "all_public":
        spec = replace(
            spec,
            requirements=tuple(
                replace(requirement, validator=_has_public_company_records)
                if requirement.key == "companies"
                else requirement
                for requirement in spec.requirements
                if requirement.key != "company_financials"
            ),
        )
    return await run_agentic_research(
        spec,
        f"请对「{name}」开展产业链动态调研。{scope_text}。形成可追溯的事实证据和研究摘要。\n{guidance}",
        settings=settings,
        event_callback=event_callback,
    )
