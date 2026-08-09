from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.agentic.events import AgentEvent
from app.agentic.public import (
    AgenticResearchResult,
    AgentResearchSpec,
    EvidenceRequirement,
    run_agentic_research,
)

INDUSTRY_CHAIN_RESEARCH_SPEC = AgentResearchSpec(
    name="industry-chain-research",
    display_name="产业链动态调研",
    system_prompt="""你是产业链研究 Agent。请围绕指定产业自主拆解研究问题，并通过工具进行多轮公开信息调研。

要求：
- 先界定产业边界、主要产品、上下游和区域口径，再调查市场、竞争、技术、公司、事件与风险。
- 使用问财工具查找结构化数据、相关公司、研报和资讯；使用 web_search 发现公开来源后，必须调用 fetch_url 或 fetch_urls 阅读正文。
- 用户未指定时间范围时，研报、新闻、政策、事件和技术动态默认限定最近半年，web_search 使用 time_range=half_year。
- 网页检索默认使用中文关键词并设置 language=zh，优先中文权威来源；英文权威材料仅作补充，最终摘要使用中文。
- 先按研究维度生成互补检索式，每个 query 只查一个问题：市场规模与增速、竞争格局与份额、技术路线与量产、政策与资本事件分别检索。
- 检索式使用“产业主题 + 具体指标/事件 + 中国或全球 + 运行时当前年份 + 研报/白皮书/公告”等有效词，禁止直接搜索整句任务或“产业链发展前景分析”等宽泛表达。
- 不得在时效性 query 中沿用旧年份；若结果主要早于最近半年，加入运行时当前年份和权威来源类型缩小范围后重新检索，不得重复原 query。
- 市场规模等低频年度数据可以使用更早资料，但必须优先最新一期并明确统计日期、区域和口径。
- 网页搜索摘要不能替代正文证据；市场规模、份额、增速和日期必须保留来源与统计口径。
- 不得调用 sector_analysis，避免产业链分析递归调用自身。
- 对冲突数据说明来源、时期和口径差异，不得编造市场份额、公司代码或事件。
- 最终摘要区分事实、推断和证据缺口。""",
    tool_names=(
        "iwencai_select_stock",
        "iwencai_query",
        "iwencai_search",
        "web_search",
        "fetch_url",
        "fetch_urls",
        "get_hot_rank",
    ),
    requirements=(
        EvidenceRequirement(
            "market_boundary",
            "市场与产业边界",
            ("iwencai_query", "web_search"),
        ),
        EvidenceRequirement(
            "companies",
            "相关公司",
            ("iwencai_select_stock", "iwencai_query"),
        ),
        EvidenceRequirement(
            "public_sources",
            "研报与公开来源",
            ("iwencai_search", "web_search"),
        ),
        EvidenceRequirement(
            "web_content",
            "网页正文证据",
            ("fetch_url", "fetch_urls"),
        ),
    ),
)


async def research_industry_chain(
    name: str,
    settings: Any = None,
    event_callback: Callable[[AgentEvent], Awaitable[None]] | None = None,
) -> AgenticResearchResult:
    return await run_agentic_research(
        INDUSTRY_CHAIN_RESEARCH_SPEC,
        f"请对「{name}」开展产业链动态调研，形成可追溯的事实证据和研究摘要。",
        settings=settings,
        event_callback=event_callback,
    )
