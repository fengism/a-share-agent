"""搜索引擎降级链的异常隔离回归。

注册期描述承诺「自动降级」，但降级循环原本没有 try/except：``provider_gateway.call``
耗尽重试会 raise、熔断时会抛 ``ProviderCircuitOpenError`` —— 第一个引擎抛异常，
360 和 Bing 根本不会被尝试，降级只在「返回空」时才成立。

同时约束另一面：**所有引擎都抛异常时必须以错误收场**，静默返回 ``count: 0``
会把「上游挂了」伪装成「确实没有相关结果」，模型就不会改用别的来源了。
"""
import pytest

from app.agentic.tools.packs.web import search as search_module
from app.agentic.tools.packs.web.search import execute_web_search
from app.core.cache import TTLCache

_RESULT = {"title": "宁德时代储能产业链", "href": "https://news.example.com/a.html", "body": "正文摘要"}


class FakeGateway:
    """按 provider 名字返回预设结果或抛预设异常；绝不触网。"""

    def __init__(self, script: dict[str, object]):
        self.script = script
        self.attempted: list[str] = []

    async def call(self, provider_name, operation, factory, *, is_fallback_attempt=False):
        self.attempted.append(provider_name)
        outcome = self.script[provider_name]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.fixture
def gateway(monkeypatch):
    def install(script: dict[str, object]) -> FakeGateway:
        fake = FakeGateway(script)
        monkeypatch.setattr(search_module, "provider_gateway", fake)
        return fake

    return install


async def _search(gateway: FakeGateway):
    return await execute_web_search("宁德时代 储能产业链", cache=TTLCache(maxsize=8, name="test_search"))


class TestFallbackSurvivesExceptions:
    async def test_primary_exception_does_not_block_fallback(self, gateway):
        fake = gateway({"baidu_search": RuntimeError("baidu 挂了"), "so360_search": [_RESULT]})
        payload = await _search(fake)
        assert payload["engine"] == "so360"
        assert payload["count"] == 1
        assert fake.attempted == ["baidu_search", "so360_search"]

    async def test_falls_through_to_third_engine(self, gateway):
        fake = gateway(
            {
                "baidu_search": RuntimeError("baidu 挂了"),
                "so360_search": TimeoutError("360 超时"),
                "bing_cn_search": [_RESULT],
            }
        )
        payload = await _search(fake)
        assert payload["engine"] == "bing_cn"
        assert payload["count"] == 1
        assert len(fake.attempted) == 3

    async def test_exception_then_empty_answer_is_a_legit_empty_result(self, gateway):
        # 至少有一个引擎正常回了话，0 条就是 0 条，不该升级成错误。
        fake = gateway(
            {"baidu_search": RuntimeError("baidu 挂了"), "so360_search": [], "bing_cn_search": []}
        )
        payload = await _search(fake)
        assert payload["count"] == 0
        assert payload["results"] == []

    async def test_all_engines_empty_is_not_an_error(self, gateway):
        fake = gateway({"baidu_search": [], "so360_search": [], "bing_cn_search": []})
        payload = await _search(fake)
        assert payload["count"] == 0
        assert len(fake.attempted) == 3

    async def test_primary_success_skips_fallback(self, gateway):
        fake = gateway({"baidu_search": [_RESULT]})
        payload = await _search(fake)
        assert payload["engine"] == "baidu"
        assert fake.attempted == ["baidu_search"]


class TestAllEnginesDownIsAnError:
    async def test_every_engine_raising_propagates(self, gateway):
        # 全挂必须抛出去，让 Tool.execute 落成 is_error，而不是返回空结果。
        fake = gateway(
            {
                "baidu_search": RuntimeError("baidu 挂了"),
                "so360_search": TimeoutError("360 超时"),
                "bing_cn_search": RuntimeError("bing 挂了"),
            }
        )
        with pytest.raises((RuntimeError, TimeoutError)):
            await _search(fake)
        assert len(fake.attempted) == 3

    async def test_last_engine_error_is_the_one_raised(self, gateway):
        # 断言异常类型：只断言 is_error 的话，脚本漏键导致的 KeyError 也会让测试变绿，
        # 于是「降级第三跳」实际从未被验证过。
        fake = gateway(
            {
                "baidu_search": RuntimeError("baidu 挂了"),
                "so360_search": RuntimeError("360 挂了"),
                "bing_cn_search": RuntimeError("bing 挂了"),
            }
        )
        with pytest.raises(RuntimeError, match="bing 挂了"):
            await _search(fake)
        assert fake.attempted == ["baidu_search", "so360_search", "bing_cn_search"]

    async def test_tool_layer_reports_it_as_an_error(self, gateway, application_handlers):
        from app.agentic.catalog import registry
        from app.agentic.events import _tool_result_summary
        from app.agentic.protocol import ToolCallInfo
        from app.agentic.tools.registration import register_all_tools

        register_all_tools()
        gateway(
            {
                "baidu_search": RuntimeError("baidu 挂了"),
                "so360_search": RuntimeError("360 挂了"),
                "bing_cn_search": RuntimeError("bing 挂了"),
            }
        )
        tool = registry.get_tool("web_search")
        result = await tool.execute(
            ToolCallInfo(id="c1", function={"name": "web_search", "arguments": '{"query": "宁德时代"}'})
        )
        assert result.is_error is True
        assert _tool_result_summary(result).summary != "调用完成"
