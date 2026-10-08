"""港股行业对比（F10 行业地位与同业公司指标）测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agentic.bootstrap import register_all_capabilities
from app.agentic.catalog import registry
from app.core.cache import analysis_cache, market_cache, reference_cache, series_cache
from app.financial_data.hk.industry_comparison import (
    HKIndustryComparison,
    HKIndustryPeerItem,
    get_hk_stock_industry_comparison,
)
from app.financial_data.stock.valuation.detail import get_valuation_detail
from app.financial_data.stock.valuation.orchestrator import get_valuation
from app.infrastructure.providers.ths.hk_field import (
    _parse_row,
    fetch_hk_industry_comparison,
)
from app.infrastructure.providers.ths.transport import ThsTransport


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


def test_parse_row_handles_loss_and_formatting():
    """验证单行数据解析能够正确识别亏损 PE、安全转换浮点并规范化 5 位港股代码。"""
    normal_row = [
        "9999", "网易", "32.20", "2681.77", "16.18", "3.12",
        "2218.15", "700.40", "26.1173", "208.02",
    ]
    parsed_normal = _parse_row(normal_row)
    assert parsed_normal["code"] == "09999"
    assert parsed_normal["name"] == "网易"
    assert parsed_normal["total_shares"] == 32.20
    assert parsed_normal["total_assets"] == 2681.77
    assert parsed_normal["pe"] == 16.18
    assert parsed_normal["is_pe_loss"] is False
    assert parsed_normal["pb"] == 3.12
    assert parsed_normal["current_assets"] == 2218.15
    assert parsed_normal["total_liabilities"] == 700.40
    assert parsed_normal["debt_to_assets_ratio"] == 26.12
    assert parsed_normal["net_profit"] == 208.02

    loss_row = [
        "302", "中手游", "31.18", "37.56", "亏损", "0.20",
        "9.45", "10.83", "28.8418", "-1.04",
    ]
    parsed_loss = _parse_row(loss_row)
    assert parsed_loss["code"] == "00302"
    assert parsed_loss["name"] == "中手游"
    assert parsed_loss["pe"] is None
    assert parsed_loss["is_pe_loss"] is True
    assert parsed_loss["pb"] == 0.20
    assert parsed_loss["net_profit"] == -1.04


def test_fetch_hk_industry_comparison_mock_soup():
    """验证从 mock HTML 文档提取行业分类路径、总数以及报告期数据。"""
    mock_html = """
    <html>
    <body>
        <p class="threecate"><span>资讯科技业 - 软件服务 - 游戏软件（共24家）</span></p>
        <div id="fieldsChartData" style="display:none">
        {
            "2026中报": [
                ["09999","网易","32.20","2681.77","16.18","3.12","2218.15","700.40","26.1173","208.02"],
                ["00302","中手游","31.18","37.56","亏损","0.20","9.45","10.83","28.8418","-1.04"]
            ],
            "2025年报": [
                ["09999","网易","32.20","2467.45","16.18","3.12","2012.77","627.53","25.4323","387.79"]
            ]
        }
        </div>
    </body>
    </html>
    """
    transport = ThsTransport()
    with patch(
        "app.infrastructure.providers.ths.hk_field.fetch_ths_f10_page",
        return_value=pytest.importorskip("bs4").BeautifulSoup(mock_html, "html.parser"),
    ):
        data = fetch_hk_industry_comparison(transport, "09999")

    assert data["code"] == "09999"
    assert data["industry"] == "资讯科技业"
    assert data["sub_industry"] == "软件服务"
    assert data["segment"] == "游戏软件"
    assert data["company_count"] == 24
    assert data["periods"] == ["2026中报", "2025年报"]
    assert len(data["period_data"]["2026中报"]) == 2
    assert len(data["period_data"]["2025年报"]) == 1


@pytest.mark.asyncio
async def test_get_hk_stock_industry_comparison_service():
    """验证服务层支持获取行业对比并切换不同报告期。"""
    mock_comparison = HKIndustryComparison(
        code="09999",
        industry="资讯科技业",
        sub_industry="软件服务",
        segment="游戏软件",
        industry_path="资讯科技业 - 软件服务 - 游戏软件",
        company_count=24,
        periods=["2026中报", "2025年报"],
        current_period="2026中报",
        peers=[
            HKIndustryPeerItem(code="09999", name="网易", pe=16.18, pb=3.12),
            HKIndustryPeerItem(code="00302", name="中手游", pe=None, is_pe_loss=True, pb=0.20),
        ],
        all_period_data={
            "2026中报": [
                HKIndustryPeerItem(code="09999", name="网易", pe=16.18, pb=3.12),
                HKIndustryPeerItem(code="00302", name="中手游", pe=None, is_pe_loss=True, pb=0.20),
            ],
            "2025年报": [
                HKIndustryPeerItem(code="09999", name="网易", pe=15.0, pb=3.0),
            ],
        },
        source="ths",
    )

    with patch(
        "app.financial_data.hk.industry_comparison._fetch_hk_industry_comparison_remote",
        new=AsyncMock(return_value=mock_comparison),
    ):
        # 默认最新期
        res1 = await get_hk_stock_industry_comparison("09999")
        assert res1.current_period == "2026中报"
        assert len(res1.peers) == 2

        # 切换报告期
        res2 = await get_hk_stock_industry_comparison("09999", period="2025年报")
        assert res2.current_period == "2025年报"
        assert len(res2.peers) == 1
        assert res2.peers[0].pe == 15.0


@pytest.mark.asyncio
async def test_hk_valuation_integrates_industry_peers():
    """验证估值模块在加载港股估值时会自动聚合行业同业对比数据并计算中位数。"""
    mock_comparison = HKIndustryComparison(
        code="00700",
        industry="资讯科技业",
        sub_industry="软件服务",
        segment="数码解决方案服务",
        industry_path="资讯科技业 - 软件服务 - 数码解决方案服务",
        company_count=2,
        periods=["2026中报"],
        current_period="2026中报",
        peers=[
            HKIndustryPeerItem(code="00700", name="腾讯控股", pe=22.5, pb=3.8),
            HKIndustryPeerItem(code="09660", name="地平线机器人-W", pe=None, is_pe_loss=True, pb=3.37),
            HKIndustryPeerItem(code="00388", name="香港交易所", pe=30.0, pb=7.5),
        ],
        all_period_data={},
    )

    with patch(
        "app.financial_data.hk.industry_comparison.get_hk_stock_industry_comparison",
        new=AsyncMock(return_value=mock_comparison),
    ):
        # 1. 测试 orchestrator.get_valuation 填充了 peers
        val = await get_valuation("00700")
        assert len(val.peers) >= 1
        assert any(p.code == "00388" for p in val.peers)

        # 2. 测试 valuation detail 计算了 peer_summary
        detail = await get_valuation_detail("00700")
        assert detail.industry == "资讯科技业 - 软件服务 - 数码解决方案服务"
        assert detail.peer_summary.peer_count >= 1
        assert len(detail.peer_summary.peers) >= 1


def test_tool_and_skill_registration():
    """验证 get_hk_stock_industry_comparison 工具与技能注册无缝。"""
    register_all_capabilities()
    unassigned = registry.validate_skill_coverage()
    assert unassigned == []

    tool = registry.get_tool("get_hk_stock_industry_comparison")
    assert tool is not None
    assert "港股" in tool.description

    skills = {s.name: s for s in registry.list_skills()}
    stock_skill = skills["stock_analysis"]
    assert "get_hk_stock_industry_comparison" in stock_skill.tool_names
