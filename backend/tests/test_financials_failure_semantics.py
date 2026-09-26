"""analyze_financials 的故障语义回归护栏。

核心约束：核心分片（三张表 + 关键指标）全部取不到时，工具必须报失败，
不能返回 ok:true + 全 null。否则 Agent 会认为调用成功而原地重试，
产业链的证据校验又永远不通过，最终耗尽 max_rounds。
"""

import pytest

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallInfo
from app.agentic.tools.packs.stock import helpers
from app.agentic.tools.registration import register_all_tools
from app.agentic.tools.serialization import serialize_result

_CORE_CALLS = ("get_stock_financial", "get_stock_financial_metrics")

# 最小可用的报表行：只需让 _report_metadata 取到报告期、利润表有营收字段，
# 从而构造出「核心分片正常」的场景，避免测试依赖真实网络。
_ROW = {
    "REPORT_DATE": "2026-06-30",
    "REPORT_DATE_NAME": "2026半年报",
    "CURRENCY": "CNY",
    "OPERATE_INCOME": 1_000_000_000.0,
    "PARENT_NETPROFIT": 120_000_000.0,
    "OPERATE_PROFIT": 150_000_000.0,
    "BASIC_EPS": 1.2,
    "TOTAL_ASSETS": 5_000_000_000.0,
    "TOTAL_LIABILITIES": 2_000_000_000.0,
}


@pytest.fixture
def tool():
    register_all_tools()
    return registry.get_tool("analyze_financials")


@pytest.fixture
def healthy_core(monkeypatch):
    """把四个核心分片桩成正常数据，只让主营构成按用例要求变化。"""

    async def _financial(_code, indicator="balance", **_kwargs):
        return [dict(_ROW)]

    async def _metrics(_code, **_kwargs):
        return {"净资产收益率": 12.5}

    monkeypatch.setattr(helpers, "get_stock_financial", _financial)
    monkeypatch.setattr(helpers, "get_stock_financial_metrics", _metrics)
    return monkeypatch


async def _invoke(tool, code: str = "600519"):
    import json

    call = ToolCallInfo(
        id="c1",
        function={"name": "analyze_financials", "arguments": json.dumps({"code": code})},
    )
    return await registry.execute_tool(call)


def _payload(result) -> dict:
    import json

    return json.loads(result.content)


class TestTotalUpstreamFailure:
    async def test_reports_error_instead_of_silent_nulls(self, tool, monkeypatch):
        async def boom(*_args, **_kwargs):
            raise RuntimeError("模拟新浪不可达")

        for name in (*_CORE_CALLS, "get_stock_revenue_breakdown"):
            monkeypatch.setattr(helpers, name, boom)

        result = await _invoke(tool)
        payload = _payload(result)

        assert result.is_error is True
        assert payload["ok"] is False
        assert payload["error"]["retryable"] is False

    async def test_error_tells_model_to_switch_source(self, tool, monkeypatch):
        async def boom(*_args, **_kwargs):
            raise RuntimeError("模拟新浪不可达")

        for name in (*_CORE_CALLS, "get_stock_revenue_breakdown"):
            monkeypatch.setattr(helpers, name, boom)

        payload = _payload(await _invoke(tool))
        message = payload["error"]["message"]
        # 必须明确「不是该公司没有数据」，否则模型会当成客观结论继续推理
        assert "不是该公司没有财务数据" in message
        # 必须给出可执行的替代路径，并劝阻原地重试
        assert "不要用相同参数重复调用" in message
        assert "get_stock_financial" in message

    async def test_records_upstream_error_types(self, tool, monkeypatch):
        async def boom(*_args, **_kwargs):
            raise TimeoutError("模拟超时")

        for name in (*_CORE_CALLS, "get_stock_revenue_breakdown"):
            monkeypatch.setattr(helpers, name, boom)

        payload = _payload(await _invoke(tool))
        assert payload["data"]["upstream_errors"]["profit"] == "TimeoutError"
        assert set(payload["data"]["unavailable_sections"]) >= {"balance", "profit", "cashflow", "metrics"}

    async def test_error_code_is_stable(self, tool, monkeypatch):
        async def boom(*_args, **_kwargs):
            raise RuntimeError("x")

        for name in (*_CORE_CALLS, "get_stock_revenue_breakdown"):
            monkeypatch.setattr(helpers, name, boom)

        payload = _payload(await _invoke(tool))
        assert payload["data"]["error_code"] == "upstream_unavailable"


class TestRevenueBreakdownAloneUnavailable:
    async def test_empty_breakdown_does_not_fail_the_call(self, tool, healthy_core):
        # 新浪 getGrossRevenue 常年为空属正常，不能因为它缺就把整次调用判死。
        async def empty(*_args, **_kwargs):
            return {}

        healthy_core.setattr(helpers, "get_stock_revenue_breakdown", empty)

        payload = _payload(await _invoke(tool))
        assert payload["ok"] is True
        assert "error" not in payload
        assert "revenue_breakdown" in payload["data"]["unavailable_sections"]

    async def test_healthy_call_reports_data(self, tool, healthy_core):
        async def breakdown(*_args, **_kwargs):
            return {"status": "unavailable"}

        healthy_core.setattr(helpers, "get_stock_revenue_breakdown", breakdown)

        payload = _payload(await _invoke(tool))
        assert payload["ok"] is True
        assert payload["data"]["report_date"] == "2026半年报"
        assert payload["data"]["income"]["revenue_billion"] == pytest.approx(10.0)


class TestSerializeContract:
    def test_error_key_makes_result_non_retryable(self):
        from app.agentic.tools.serialization import result_error_message

        failed = {
            "code": "600519",
            "error": "上游不可用",
            "error_code": "upstream_unavailable",
            "unavailable_sections": ["profit"],
        }
        assert result_error_message(failed) == "上游不可用"
        content = serialize_result(failed)
        assert '"retryable": false' in content
