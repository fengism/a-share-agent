"""行业韭菜指数服务与接口测试。"""

import pytest

from app.modules.sentiment.factors.crowd import calculate_crowd_and_trap_factors
from app.modules.sentiment.schemas import LeekIndexHistoryResponse, LeekIndexOverviewResponse
from app.modules.sentiment.service import LeekIndexService


@pytest.mark.asyncio
async def test_calculate_crowd_and_trap_factors_logic():
    raw_flows = {
        "电子": {
            "main_net": -500_000_000.0,
            "small_net": 600_000_000.0,
            "change_pct": 3.0,
        },
        "银行": {
            "main_net": 300_000_000.0,
            "small_net": -200_000_000.0,
            "change_pct": -2.5,
        },
    }
    guba_scores = {"电子": 90.0, "银行": 10.0}

    crowd, trap, signals = calculate_crowd_and_trap_factors(raw_flows, guba_scores)

    # 电子板块：大涨、高舆论 -> 高拥挤度与高风险
    assert crowd["电子"] > crowd["银行"]
    assert trap["电子"] > trap["银行"]
    assert len(signals["电子"]) > 0

    # 银行板块：散户割肉、主力承接 -> 筹码出清特征
    assert trap["银行"] <= 30.0


@pytest.mark.asyncio
async def test_leek_index_service_compute_and_history(tmp_path, monkeypatch):
    import app.modules.sentiment.service as s_mod

    # 将数据目录指向 tmp_path
    monkeypatch.setattr(s_mod, "_SENTIMENT_DATA_DIR", tmp_path)

    service = LeekIndexService()

    # 模拟基础数据返回
    async def mock_flows():
        return (
            {"电子": 85.0, "食品饮料": 30.0},
            {
                "电子": {"main_net": -100.0, "small_net": 120.0, "change_pct": 1.2},
                "食品饮料": {"main_net": 80.0, "small_net": -50.0, "change_pct": -0.8},
            },
        )

    monkeypatch.setattr(s_mod, "calculate_industry_fund_flow_factors", mock_flows)
    monkeypatch.setattr(
        s_mod,
        "calculate_guba_sentiment_factors",
        lambda: ({"电子": 95.0, "食品饮料": 15.0}, {}),
    )

    overview = await service.get_overview(force_refresh=True)
    assert isinstance(overview, LeekIndexOverviewResponse)
    assert len(overview.industries) >= 2

    elec = next(i for i in overview.industries if i.industry_name == "电子")
    food = next(i for i in overview.industries if i.industry_name == "食品饮料")

    # 电子得分明显高于食品饮料
    assert elec.leek_score > food.leek_score
    assert elec.risk_level in ("fever", "extreme")
    assert food.risk_level in ("safe", "normal")
    assert 0.0 <= elec.leek_score <= 100.0
    assert 0.0 <= food.leek_score <= 100.0

    # 验证历史时序
    history = await service.get_history("电子", days=7)
    assert isinstance(history, LeekIndexHistoryResponse)
    assert history.industry_name == "电子"
    assert len(history.history) >= 1
    assert history.history[0].score == elec.leek_score
