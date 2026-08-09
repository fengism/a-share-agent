from __future__ import annotations

from typing import Any

from app.agentic.public import (
    AgenticResearchResult,
    AgentResearchSpec,
    EvidenceRequirement,
    run_agentic_research,
)

ANALYSIS_RESEARCH_SPEC = AgentResearchSpec(
    name="stock-analysis-research",
    display_name="个股动态调研",
    system_prompt="""你是严谨的 A 股研究 Agent。你的任务是围绕指定股票和分析日期自主规划调研，并通过工具获取可验证证据。

要求：
- 自主决定工具调用顺序，可多轮调用并根据结果补充调查。
- 覆盖基础信息、估值与财务、技术面、新闻与情绪、风险、市场环境六个维度。
- 财务和技术判断必须基于工具返回的具体数据；新闻需关注发布日期和来源。
- 对冲突信息指出口径差异，不得使用常识补写工具未返回的事实。
- 最终摘要区分事实、推断与数据缺口，并说明最重要的多空证据。""",
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
    ),
    requirements=(
        EvidenceRequirement("profile", "基础信息", ("get_stock_info",)),
        EvidenceRequirement(
            "fundamental",
            "估值与财务",
            ("get_stock_valuation_detail", "analyze_financials"),
        ),
        EvidenceRequirement(
            "technical",
            "技术面",
            ("get_stock_technical_indicators", "get_stock_kline"),
        ),
        EvidenceRequirement(
            "sentiment",
            "新闻与情绪",
            ("get_stock_news", "get_stock_sentiment"),
        ),
        EvidenceRequirement("risk", "风险", ("get_stock_risk_data",)),
        EvidenceRequirement("market", "市场环境", ("get_market_overview",)),
    ),
)


async def research_stock(
    code: str,
    analysis_date: str,
    settings: Any = None,
) -> AgenticResearchResult:
    return await run_agentic_research(
        ANALYSIS_RESEARCH_SPEC,
        f"请动态调研股票 {code}，分析日期为 {analysis_date}。完成全维度证据采集并给出研究摘要。",
        settings=settings,
    )
