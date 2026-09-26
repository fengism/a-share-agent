"""Schema 与 executor 的双向一致性护栏。

原本只有单向校验（Schema 参数 executor 必须收），漏掉的反方向是这样一类 bug：
**下游支持、Schema 却没声明** —— 模型照着返回体里的 ``page`` 传翻页参数，
被 ``additionalProperties: false`` 直接判成「包含未声明参数」，而下游
``filter_data.setdefault("page", 1)`` 明明在翻页。

同理，``**kwargs`` 执行器让反向校验在结构上无法进行：签名里看不到任何参数名，
漏参永远不会被发现。因此注册期直接拒绝。
"""
import asyncio
import inspect

import pytest

from app.agentic.catalog import registry
from app.agentic.protocol import ToolCallInfo
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.agentic.tools.registration import register_all_tools
from app.agentic.tools.validation import validate_executor_contract
from app.modules.screener.schemas import ScreenerFilter


class TestBothDirectionsEnforced:
    def test_every_registered_tool_is_symmetric(self):
        register_all_tools()
        # 断言具体工具名而不是数量魔法：数量不校验完整性，测试顺序变化时还会假绿。
        expected = {
            "analyze_stock",
            "analyze_financials",
            "screen_stocks",
            "web_search",
            "web_fetch",
            "fetch_urls",
            "read_pdf",
            "get_stock_kline",
            "get_stock_documents",
            "get_daily_review",
            "financial_calculator",
            "python_interpreter",
        }
        assert expected <= set(registry._tools)
        for tool in registry._tools.values():
            validate_executor_contract(tool)

    def test_no_registered_tool_hides_behind_kwargs(self):
        register_all_tools()
        offenders = [
            tool.name
            for tool in registry._tools.values()
            if tool.executor is not None
            and any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in inspect.signature(tool.executor).parameters.values()
            )
        ]
        assert offenders == []

    def test_schema_parameter_missing_from_executor_is_rejected(self):
        # 原有方向，不能为了加新检查把它弄丢。
        async def only_code(code: str) -> dict:
            return {"code": code}

        tool = Tool(
            name="stub_dir_a",
            description="测试用",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["code"],
            },
            executor=only_code,
        )
        with pytest.raises(ValueError, match="未被 executor 接收"):
            registry.register_tool(tool)

    def test_executor_parameter_missing_from_schema_is_rejected(self):
        async def code_and_page(code: str, page: int = 1) -> dict:
            return {"code": code, "page": page}

        tool = Tool(
            name="stub_dir_b",
            description="测试用",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
            executor=code_and_page,
        )
        with pytest.raises(ValueError, match="未在 Schema 声明"):
            registry.register_tool(tool)

    def test_kwargs_executor_is_rejected(self):
        async def anything(**kwargs) -> dict:
            return dict(kwargs)

        tool = Tool(
            name="stub_dir_c",
            description="测试用",
            parameters={"type": "object", "properties": {"code": {"type": "string"}}},
            executor=anything,
        )
        with pytest.raises(ValueError, match=r"\*\*kwargs"):
            registry.register_tool(tool)

    def test_positional_only_executor_is_rejected(self):
        # Tool.execute 一律 executor(**arguments)：位置-only 参数注册期能过、运行时
        # 必 TypeError，所以必须在注册期就拒。
        async def posonly(code: str, /) -> dict:
            return {"code": code}

        tool = Tool(
            name="stub_dir_e",
            description="测试用",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
            executor=posonly,
        )
        with pytest.raises(ValueError, match="位置-only"):
            registry.register_tool(tool)

    def test_var_positional_executor_is_rejected(self):
        # *args 与 **kwargs 作用相同：反向校验看不到任何参数名。
        async def varargs(code: str, *rest) -> dict:
            return {"code": code}

        tool = Tool(
            name="stub_dir_f",
            description="测试用",
            parameters={
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
            executor=varargs,
        )
        with pytest.raises(ValueError, match=r"\*args"):
            registry.register_tool(tool)

    def test_executor_required_parameter_must_be_declared_required(self):
        async def required_code(code: str) -> dict:
            return {"code": code}

        tool = Tool(
            name="stub_dir_d",
            description="测试用",
            parameters={"type": "object", "properties": {"code": {"type": "string"}}},
            executor=required_code,
        )
        with pytest.raises(ValueError, match="必填参数未在 Schema required 声明"):
            registry.register_tool(tool)


class TestScreenStocksCoverDownstreamFilters:
    def test_schema_matches_screener_filter_fields(self):
        # 双向一致性的最终落点：Schema 要覆盖 ScreenerFilter 能收的每一个字段。
        register_all_tools()
        tool = registry.get_tool("screen_stocks")
        assert set(tool.parameters["properties"]) == set(ScreenerFilter.model_fields)

    @pytest.mark.parametrize(
        "name",
        ["page", "page_size", "markets", "exclude_st", "min_listing_days", "min_amount_yi"],
    )
    def test_previously_missing_fields_are_declared(self, name):
        register_all_tools()
        assert name in registry.get_tool("screen_stocks").parameters["properties"]

    def test_pagination_is_reachable_end_to_end(self, monkeypatch, application_handlers):
        from app.runtime import agentic_tools as runtime

        register_all_tools()

        captured: dict = {}

        class _FakeResult:
            def __init__(self, filters: ScreenerFilter):
                self.filters = filters

            def model_dump(self):
                return {"count": 0, "page": self.filters.page, "page_size": self.filters.page_size}

        async def _fake_screen(filters: ScreenerFilter) -> _FakeResult:
            captured.update(filters.model_dump())
            return _FakeResult(filters)

        monkeypatch.setattr(runtime, "screen_stocks", _fake_screen)

        result = asyncio.run(
            registry.get_tool("screen_stocks").execute(
                ToolCallInfo(
                    id="c1",
                    function={
                        "name": "screen_stocks",
                        "arguments": (
                            '{"page": 3, "page_size": 50, "markets": ["主板"],'
                            ' "exclude_st": true, "min_amount_yi": 2}'
                        ),
                    },
                )
            )
        )
        assert result.is_error is False, result.content
        assert captured["page"] == 3
        assert captured["page_size"] == 50
        assert captured["markets"] == ["主板"]
        assert captured["exclude_st"] is True
        assert captured["min_amount_yi"] == 2


class TestDailyReviewDeclaresForce:
    def test_force_is_reachable(self):
        register_all_tools()
        tool = registry.get_tool("get_daily_review")
        assert "force" in tool.parameters["properties"]
        assert tool.parameters["properties"]["force"]["type"] == "boolean"


class TestRegistryIsNotPolluted:
    """注册失败不能留下残骸——registry 是全局单例，泄漏会污染后续测试。"""

    def test_failed_registrations_leave_the_registry_untouched(self):
        register_all_tools()
        before = set(registry._tools)

        async def only_code(code: str) -> dict:
            return {"code": code}

        async def code_and_page(code: str, page: int = 1) -> dict:
            return {"code": code, "page": page}

        async def anything(**kwargs) -> dict:
            return dict(kwargs)

        async def posonly(code: str, /) -> dict:
            return {"code": code}

        async def varargs(code: str, *rest) -> dict:
            return {"code": code}

        broken = [
            # schema 多声明了 limit
            Tool(name="stub_pollute_a", description="d",
                 parameters={"type": "object", "properties": {"code": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["code"]},
                 executor=only_code),
            # executor 有 schema 没声明的 page
            Tool(name="stub_pollute_b", description="d",
                 parameters={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
                 executor=code_and_page),
            Tool(name="stub_pollute_c", description="d",
                 parameters={"type": "object", "properties": {"code": {"type": "string"}}},
                 executor=anything),
            Tool(name="stub_pollute_d", description="d",
                 parameters={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
                 executor=posonly),
            Tool(name="stub_pollute_e", description="d",
                 parameters={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
                 executor=varargs),
        ]
        for tool in broken:
            with pytest.raises(ValueError):
                registry.register_tool(tool)
        assert set(registry._tools) == before


def test_tool_policy_still_usable():
    assert ToolPolicy(cost="low").cost == "low"
