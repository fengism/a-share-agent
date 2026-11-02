"""限售股解禁日历与抛压监测服务及 Chat 工具契约测试。"""

from unittest.mock import patch

import pytest

from app.agentic_integration.tools.packs.stock import helpers
from app.financial_data.stock.insights.restricted import get_restricted_shares_lift


@pytest.mark.asyncio
async def test_restricted_shares_lift_timeout_fallback():
    """测试限售解禁上游超时时，降级返回友好的防御性提示，而非挂起或超时失败。"""
    with patch(
        "app.infrastructure.providers.provider_gateway.provider_gateway.call_blocking",
        side_effect=TimeoutError(),
    ):
        res = await get_restricted_shares_lift("600519")
        assert res["code"] == "600519"
        assert res["has_upcoming_lifts"] is False
        assert "超时或不可用" in res["pressure_risk_assessment"]


@pytest.mark.asyncio
async def test_restricted_shares_lift_exception_fallback():
    """测试限售解禁数据源异常时，安全返回空结果与状态，不影响全流程。"""
    with patch(
        "app.infrastructure.providers.provider_gateway.provider_gateway.call_blocking",
        side_effect=RuntimeError("connection error"),
    ):
        res = await get_restricted_shares_lift("000001")
        assert res["code"] == "000001"
        assert res["has_upcoming_lifts"] is False
        assert "无近期解禁风险" in res["pressure_risk_assessment"] or "超时或不可用" in res["pressure_risk_assessment"]


@pytest.mark.asyncio
async def test_restricted_shares_lift_helper_safety():
    """测试 Chat 工具 helper 层防御兜底，遇到未捕获异常不冒泡。"""
    with patch(
        "app.financial_data.stock.insights.restricted.get_restricted_shares_lift",
        side_effect=RuntimeError("unexpected crash"),
    ):
        res = await helpers.get_restricted_shares_lift("600519")
        assert res["code"] == "600519"
        assert "限售解禁数据暂不可用" in res["pressure_risk_assessment"]


@pytest.mark.asyncio
async def test_restricted_shares_lift_hk_code():
    """测试港股代码快速返回且无阻塞。"""
    res = await get_restricted_shares_lift("00700")
    assert res["code"] == "00700"
    assert res["has_upcoming_lifts"] is False
    assert "港股暂无" in res["pressure_risk_assessment"]
