"""analyze_stock 五路全挂时必须报错。

``_gather_labeled`` 把每个分片的异常/超时降级成 ``{"status": ..., "error": ...}``，
外层只输出 ``partial`` 与 ``unavailable_sections``，**没有顶层 error** ——
于是 ``result_error_message`` 返回 None、``is_error=False``，Agent 看到「调用成功」，
拿着五个空分片当结论，或者用同样参数原地重试。这与 analyze_financials 修过的是
同一类问题；此前那次修复只落在了那一个工具上。
"""
import json

import pytest

from app.agentic.catalog import registry
from app.agentic.events import _tool_result_summary
from app.agentic.protocol import ToolCallInfo
from app.agentic.tools.packs.stock import helpers
from app.agentic.tools.registration import register_all_tools

_SECTIONS = (
    "get_stock_info",
    "get_stock_valuation_detail",
    "get_stock_technical_indicators",
    "get_stock_news",
    "get_stock_sentiment",
)


@pytest.fixture
def tool():
    register_all_tools()
    return registry.get_tool("analyze_stock")


def _stub_all(monkeypatch, factory) -> None:
    for name in _SECTIONS:
        monkeypatch.setattr(helpers, name, factory(name))


async def _run(tool):
    return await tool.execute(
        ToolCallInfo(id="c1", function={"name": "analyze_stock", "arguments": '{"code": "600519"}'})
    )


class TestAllSectionsDownIsAnError:
    async def test_every_section_raising(self, tool, monkeypatch):
        def factory(name):
            async def boom(_code):
                raise RuntimeError(f"{name} 上游挂了")

            return boom

        _stub_all(monkeypatch, factory)
        result = await _run(tool)
        assert result.is_error is True
        payload = json.loads(result.content)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "upstream_unavailable"
        assert "五个维度全部取不到" in payload["error"]["message"]
        assert "上游挂了" in payload["error"]["message"]

    async def test_every_section_returning_an_error_dict(self, tool, monkeypatch):
        def factory(name):
            async def broken(_code):
                return {"error": f"{name} 无数据"}

            return broken

        _stub_all(monkeypatch, factory)
        result = await _run(tool)
        assert result.is_error is True
        assert json.loads(result.content)["error"]["code"] == "upstream_unavailable"

    async def test_every_section_timing_out(self, tool, monkeypatch):
        import asyncio

        from app.agentic.tools.packs.composite import registration as composite

        # 用极短超时代替真实的 8~15s，避免拖慢整套测试。断言时比对 patch 之前的
        # 生产 label 集合，否则生产改成 6 个 section 而 _gather_labeled 只返回 5 个
        # label，测试照样绿。
        production_labels = list(composite._ANALYZE_SECTION_TIMEOUTS)
        monkeypatch.setattr(
            composite,
            "_ANALYZE_SECTION_TIMEOUTS",
            {label: 0.01 for label in production_labels},
        )

        def factory(name):
            async def slow(_code):
                await asyncio.sleep(30)

            return slow

        _stub_all(monkeypatch, factory)
        result = await _run(tool)
        assert result.is_error is True
        payload = json.loads(result.content)
        assert payload["error"]["code"] == "upstream_unavailable"
        assert payload["data"]["unavailable_sections"] == production_labels

    async def test_user_sees_a_specific_label_not_a_generic_one(self, tool, monkeypatch):
        def factory(name):
            async def boom(_code):
                raise RuntimeError(f"{name} 挂了")

            return boom

        _stub_all(monkeypatch, factory)
        summary = _tool_result_summary(await _run(tool))
        assert summary.summary == "数据源暂不可用"
        assert summary.status == "error"

    async def test_error_message_tells_the_model_where_to_go_next(self, tool, monkeypatch):
        def factory(name):
            async def boom(_code):
                raise RuntimeError("挂了")

            return boom

        _stub_all(monkeypatch, factory)
        payload = json.loads((await _run(tool)).content)
        assert "不要用相同参数重复调用本工具" in payload["error"]["message"]
        assert "get_stock_info" in payload["error"]["message"]


class TestPartialFailuresStillSucceed:
    async def test_single_section_down_keeps_ok_true(self, tool, monkeypatch):
        def factory(name):
            async def handle(_code):
                if name == "get_stock_news":
                    return {"error": "新闻源限流"}
                return {"ok": True, "name": name, "value": 1}

            return handle

        _stub_all(monkeypatch, factory)
        result = await _run(tool)
        assert result.is_error is False
        payload = json.loads(result.content)["data"]
        assert payload["partial"] is True
        assert payload["unavailable_sections"] == ["news"]
        assert "error" not in payload

    async def test_all_sections_healthy(self, tool, monkeypatch):
        def factory(name):
            async def handle(_code):
                return {"ok": True, "name": name}

            return handle

        _stub_all(monkeypatch, factory)
        result = await _run(tool)
        assert result.is_error is False
        payload = json.loads(result.content)["data"]
        assert payload["partial"] is False
        assert payload["unavailable_sections"] == []
        assert payload["info"]["name"] == "get_stock_info"
