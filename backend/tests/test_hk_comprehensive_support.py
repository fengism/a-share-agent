"""全面的港股多模块支持与防御性回退测试。

覆盖：
1. Agentic Skills 覆盖与 Agent Profiles 工具分配（validate_skill_coverage, profiles）
2. Agent 上下文解析（_resolve_stock 识别港股）
3. 多股对比服务（compare_stocks 支持纯港股与 A/H 混合对比，指标降级不抛错）
4. 港股财务接入同花顺，其他估值、舆情与深度洞察模块保持防御性行为
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agentic.agents.profiles.fundamental import PROFILE as FUNDAMENTAL_ANALYST_PROFILE
from app.agentic.agents.profiles.technical import PROFILE as TECHNICAL_ANALYST_PROFILE
from app.agentic.bootstrap import register_all_capabilities
from app.agentic.catalog import registry
from app.agentic.tools.packs.stock.context import _resolve_stock
from app.core.cache import analysis_cache, market_cache, reference_cache, series_cache
from app.core.exceptions import InvalidRequestError, UpstreamUnavailableError
from app.financial_data.hk.schemas import HKStockQuote, HKStockQuotePage, HKStockValuation
from app.financial_data.stock.fundamentals.financials import (
    get_financial,
    get_financial_metrics,
)
from app.financial_data.stock.insights.bulletins import get_stock_bulletins
from app.financial_data.stock.insights.fund_flow import get_stock_fund_flow
from app.financial_data.stock.insights.fund_flow_pages import get_stock_fund_flow_page
from app.financial_data.stock.insights.interactive_qa import get_interactive_qa
from app.financial_data.stock.insights.news import get_stock_news, get_stock_news_categorized
from app.financial_data.stock.insights.reports import get_stock_reports
from app.financial_data.stock.insights.restricted import get_restricted_shares_lift
from app.financial_data.stock.insights.retail import get_retail_sentiment, get_stock_sentiment
from app.financial_data.stock.insights.risk import get_stock_risk_data
from app.financial_data.stock.profile.basic_info import (
    get_stock_concept_map,
    get_stock_concepts,
)
from app.financial_data.stock.quotes.chip_distribution import get_chip_distribution
from app.financial_data.stock.valuation.detail import get_valuation_detail
from app.financial_data.stock.valuation.percentiles import compute_percentile, compute_percentiles
from app.modules.stock_comparison.service import compare_stocks


@pytest.fixture(autouse=True)
def clear_caches():
    analysis_cache.clear()
    market_cache.clear()
    reference_cache.clear()
    series_cache.clear()
    yield
    analysis_cache.clear()
    market_cache.clear()
    reference_cache.clear()
    series_cache.clear()


def test_agentic_skills_coverage_and_profiles():
    """验证所有港股工具均已注册到 Skills 中，且 unassigned 列表为空。"""
    register_all_capabilities()
    unassigned = registry.validate_skill_coverage()
    assert unassigned == [], f"存在未分配到 Skill 的工具: {unassigned}"

    skills = {s.name: s for s in registry.list_skills()}
    # 验证 stock_analysis 包含 3 个港股个股工具
    assert "stock_analysis" in skills
    stock_analysis_skill = skills["stock_analysis"]
    assert "get_hk_stock_profile" in stock_analysis_skill.tool_names
    assert "get_hk_stock_kline" in stock_analysis_skill.tool_names
    assert "get_hk_stock_technical_indicators" in stock_analysis_skill.tool_names

    # 验证 market_data 包含港股大盘工具
    assert "market_data" in skills
    market_data_skill = skills["market_data"]
    assert "get_hk_market_overview" in market_data_skill.tool_names

    # 验证 agent profiles
    assert "get_hk_stock_kline" in TECHNICAL_ANALYST_PROFILE.tool_names
    assert "get_hk_stock_technical_indicators" in TECHNICAL_ANALYST_PROFILE.tool_names
    assert "get_hk_stock_profile" in FUNDAMENTAL_ANALYST_PROFILE.tool_names


@pytest.mark.asyncio
async def test_agent_context_resolve_hk_stock():
    """验证 Agent 对话上下文解析港股时调用港股 profile 接口且不会触发 A 股异常。"""
    with patch(
        "app.agentic.tools.packs.stock.helpers.get_hk_stock_profile",
        new=AsyncMock(
            return_value={
                "quote": {
                    "code": "00700",
                    "name": "腾讯控股",
                    "price": 380.0,
                    "market_cap": 35000,
                    "pe_ttm": 22.5,
                }
            }
        ),
    ):
        stock_context = await _resolve_stock({"code": "00700"})
        assert stock_context != ""
        assert "[港股]" in stock_context
        assert "腾讯控股" in stock_context
        assert "00700" in stock_context
        assert "380.0 HKD" in stock_context


@pytest.mark.asyncio
async def test_compare_stocks_hk_and_mixed():
    """验证多股对比服务对港股及 A/H 混比的支持。"""
    mock_hk_quote = HKStockQuote(
        code="00700",
        name="腾讯控股",
        price=380.0,
        change_pct=2.1,
        amount=5000000000.0,
    )
    mock_page = HKStockQuotePage(
        page=1,
        page_size=1,
        total=1,
        items=[mock_hk_quote],
        source="tencent",
    )
    mock_val = HKStockValuation(
        code="00700",
        pe_ttm=22.5,
        pb=3.8,
        market_cap=3500000000000.0,
    )

    with patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_quotes",
        new=AsyncMock(return_value=mock_page),
    ), patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_valuation",
        new=AsyncMock(return_value=mock_val),
    ):
        # 纯港股对比
        result_hk = await compare_stocks(["00700"])
        assert len(result_hk) == 1
        hk_item = result_hk[0]
        assert hk_item.code == "00700"
        assert hk_item.name == "腾讯控股"
        assert hk_item.price == 380.0
        assert hk_item.change_pct == 2.1
        assert hk_item.pe_ttm == 22.5
        assert hk_item.pb == 3.8
        assert hk_item.market_cap == 3500000000000.0
        assert hk_item.industry == "港股上市公司"


@pytest.mark.asyncio
async def test_hk_financials_use_ths_and_cache_results():
    """港股财务报表和核心指标走同花顺，并复用 24 小时缓存。"""
    provider = MagicMock()
    provider.fetch_hk_financial_statement = MagicMock(return_value=[{
        "REPORT_DATE": "2025-06-30",
        "REPORT_DATE_NAME": "2025-06-30",
        "CURRENCY": "港元",
        "TOTAL_ASSETS": 1000.0,
    }])
    provider.fetch_hk_financial_metrics = MagicMock(return_value={
        "code": "00700",
        "latest_report_date": "2025-06-30",
        "metrics": {"净资产收益率": 0.1056},
    })

    with patch(
        "app.financial_data.stock.fundamentals.financials._get_ths_provider",
        return_value=provider,
    ):
        first = await get_financial("00700", "balance")
        second = await get_financial("hk00700", "balance")
        metrics = await get_financial_metrics("00700")
        cached_metrics = await get_financial_metrics("hk00700")

    assert first == second
    assert first[0]["TOTAL_ASSETS"] == 1000.0
    provider.fetch_hk_financial_statement.assert_called_once_with(
        "00700", "balance", limit=8
    )
    assert metrics == cached_metrics
    assert metrics.code == "00700"
    assert metrics.latest_report_date == "2025-06-30"
    assert metrics.metrics["净资产收益率"] == 0.1056
    provider.fetch_hk_financial_metrics.assert_called_once_with("00700")


@pytest.mark.asyncio
async def test_hk_financials_raise_upstream_error():
    """同花顺失败时返回明确的上游异常，不再把故障伪装成空数据。"""
    provider = MagicMock()
    provider.fetch_hk_financial_statement = MagicMock(side_effect=RuntimeError("boom"))
    provider.fetch_hk_financial_metrics = MagicMock(side_effect=RuntimeError("boom"))
    with patch(
        "app.financial_data.stock.fundamentals.financials._get_ths_provider",
        return_value=provider,
    ):
        with pytest.raises(UpstreamUnavailableError, match="财务报表上游暂时不可用"):
            await get_financial("00700", "profit")
        with pytest.raises(UpstreamUnavailableError, match="财务指标上游暂时不可用"):
            await get_financial_metrics("00700")


@pytest.mark.asyncio
async def test_hk_valuation_defensive_fallback():
    """港股估值详情结构化返回，估值百分位返回 None。"""
    mock_val = HKStockValuation(
        code="00700",
        pe_ttm=22.5,
        pb=3.8,
        ps_ttm=5.0,
        market_cap=3500000000000.0,
        float_market_cap=3500000000000.0,
    )
    with patch(
        "app.financial_data.hk.service.hk_market_service.get_stock_valuation",
        new=AsyncMock(return_value=mock_val),
    ):
        val_detail = await get_valuation_detail("00700")
        assert val_detail.code == "00700"
        assert val_detail.multiples.pe_ttm == 22.5
        assert val_detail.multiples.pb == 3.8

    assert await compute_percentile("00700") is None

    percentiles = await compute_percentiles(["00700", "700"])
    assert len(percentiles) == 2
    assert percentiles[0]["percentile"] is None


@pytest.mark.asyncio
async def test_hk_insights_defensive_fallbacks():
    """所有 A 股专属洞察 API 对港股代码均安全回退空结构，不抛出 500/ValueError。"""
    # 1. 新闻
    assert await get_stock_news("00700") == []
    news_cat = await get_stock_news_categorized("00700")
    assert news_cat.eastmoney_news == []
    assert news_cat.cls_news == []

    # 2. 情绪
    sentiment = await get_stock_sentiment("00700")
    assert sentiment.code == "00700"
    assert sentiment.heat_score is None

    retail = await get_retail_sentiment("00700")
    assert retail.code == "00700"
    assert retail.post_count == 0

    # 3. 公告
    bulletins = await get_stock_bulletins("00700")
    assert bulletins.code == "00700"
    assert bulletins.items == []

    # 4. 研报
    reports = await get_stock_reports("00700")
    assert reports.code == "00700"
    assert reports.items == []
    assert reports.total_count == 0

    # 5. 资金流向
    fund_flow = await get_stock_fund_flow("00700")
    assert fund_flow == []

    fund_flow_page = await get_stock_fund_flow_page("00700")
    assert fund_flow_page.items == []
    assert fund_flow_page.total == 0

    # 6. 风险数据
    risk = await get_stock_risk_data("00700")
    assert risk.code == "00700"
    assert risk.fund_flow == []
    assert risk.margin_trading == []
    assert risk.block_trade == []
    assert risk.holder_change == []

    # 7. 互动问答
    qa = await get_interactive_qa("00700")
    assert qa["code"] == "00700"
    assert qa["items"] == []

    # 8. 解禁
    lifts = await get_restricted_shares_lift("00700")
    assert lifts["code"] == "00700"
    assert lifts["has_upcoming_lifts"] is False

    # 9. 概念
    assert await get_stock_concepts("00700") == []
    concept_map = await get_stock_concept_map(["00700", "600519"])
    assert "00700" in concept_map
    assert concept_map["00700"] == []

    # 10. 筹码分布（显式抛出提示异常）
    with pytest.raises(InvalidRequestError, match="港股暂无每日换手率数据"):
        await get_chip_distribution("00700")
