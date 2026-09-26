"""模型请求超时必须服从外层请求预算的回归护栏。

真实事故：chat 报「基本面分析暂时不可用」，根因是子 Agent 的最终回答轮被传输层掐断——
``openai.APITimeoutError: Request timed out`` 在 180.0 秒触发，而这次调用真正拿到的生成
预算是 1200 秒、外层对话总时限是 300 秒。

三层时限不叠 ladders 时，最内层的 ``llm_timeout_seconds`` 先触发，失败原因被误报成
「读取响应超时」，看起来像网关故障，实际只是「这次回答还没写完」。工具调用早就用
``bounded_timeout`` 跟着执行上下文的 deadline 收缩了，模型调用却一直按客户端构造时固定
的值掐断——它是预算链上唯一脱离 deadline 的一环。
"""
from types import SimpleNamespace

import pytest

from app.agentic.agents.executor import _llm_request_timeout
from app.agentic.runtime.context import AgentExecutionContext
from app.configuration.schema import Settings
from app.infrastructure.llm.completion import create_chat_completion
from app.infrastructure.llm.runtime import LiteLLMAsyncCompletions


class _RecordingResponse:
    """满足 validate_chat_completion_response / normalize_chat_completion 的最小形状。"""

    def __init__(self) -> None:
        message = SimpleNamespace(content="ok", reasoning_content=None, tool_calls=None)
        self.choices = [SimpleNamespace(message=message, delta=None, finish_reason="stop")]
        self.usage = None


class _RecordingCompletions:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return _RecordingResponse()


class _RecordingClient:
    def __init__(self) -> None:
        self.completions = _RecordingCompletions()
        self.chat = type("_Chat", (), {"completions": self.completions})()


def _settings(**overrides) -> Settings:
    return Settings(**{"llm_timeout_seconds": 180, "llm_generation_timeout_seconds": 1200.0, **overrides})


def _context(total_timeout_seconds: float | None = None, **overrides) -> AgentExecutionContext:
    return AgentExecutionContext.from_current(
        _settings(**overrides), total_timeout_seconds=total_timeout_seconds
    )


class _NullSlot:
    async def __aenter__(self) -> "_NullSlot":
        return self

    async def __aexit__(self, *_args) -> bool:
        return False


@pytest.fixture
def unblocked_limiter(monkeypatch):
    """隔离全局并发槽位：它读的是进程级设置，不该进单测。"""
    monkeypatch.setattr(
        "app.infrastructure.llm.completion._llm_limiter.slot", lambda **_kwargs: _NullSlot()
    )


class TestRequestTimeoutResolution:
    def test_falls_back_to_generation_budget_without_a_deadline(self):
        context = _context()
        assert _llm_request_timeout(context, context.settings) == 1200.0

    def test_never_outlives_the_enclosing_request_budget(self):
        context = _context(total_timeout_seconds=300.0)
        timeout = _llm_request_timeout(context, context.settings)
        # 生成预算是天花板，外层请求预算是地板：这里 300 < 1200，听外层的。
        assert timeout <= 300.0
        assert timeout > 0.0

    def test_never_shrinks_below_the_client_default(self):
        # 外层预算很宽裕时也不能低于客户端默认值，否则等于自己把传输层掐得更早。
        context = _context(total_timeout_seconds=3600.0)
        timeout = _llm_request_timeout(context, context.settings)
        assert timeout >= context.settings.llm_timeout_seconds

    def test_expired_deadline_does_not_produce_an_instant_timeout(self):
        context = _context(total_timeout_seconds=0.0)
        # deadline 已耗尽时给 1 秒兜底，让既有的 deadline 判定去报错，
        # 而不是变成一个看不懂的「读取响应超时」。
        assert _llm_request_timeout(context, context.settings) >= 1.0

    def test_generation_budget_still_wins_when_it_is_tighter(self):
        context = _context(
            total_timeout_seconds=300.0, llm_generation_timeout_seconds=90.0
        )
        assert _llm_request_timeout(context, context.settings) == 90.0


class TestPerRequestTimeoutIsForwarded:
    async def test_reaches_the_transport(self, unblocked_limiter):
        client = _RecordingClient()
        await create_chat_completion(
            client,
            model="test-model",
            messages=[],
            temperature=0.1,
            stream=False,
            request_timeout=600.0,
        )
        # 不显式传就沿用客户端默认值，显式传了必须到传输层。
        assert client.completions.kwargs["timeout"] == 600.0

    async def test_is_absent_when_not_requested(self, unblocked_limiter):
        client = _RecordingClient()
        await create_chat_completion(
            client, model="test-model", messages=[], temperature=0.1, stream=False
        )
        assert "timeout" not in client.completions.kwargs


class TestLiteLLMRespectsCallerTimeout:
    """LiteLLM 适配器原先无条件覆盖 timeout，会把抬高后的上限静默按回默认。"""

    @staticmethod
    def _adapter() -> LiteLLMAsyncCompletions:
        return LiteLLMAsyncCompletions(
            api_key="k", base_url=None, api_version="", timeout=180.0, model="m"
        )

    async def test_keeps_an_explicit_timeout(self, monkeypatch):
        captured: dict = {}

        async def fake_acompletion(**kwargs):
            captured.update(kwargs)
            return object()

        monkeypatch.setattr("litellm.acompletion", fake_acompletion)
        await self._adapter().create(model="m", messages=[], timeout=600.0)
        assert captured["timeout"] == 600.0

    async def test_uses_the_client_default_otherwise(self, monkeypatch):
        captured: dict = {}

        async def fake_acompletion(**kwargs):
            captured.update(kwargs)
            return object()

        monkeypatch.setattr("litellm.acompletion", fake_acompletion)
        await self._adapter().create(model="m", messages=[])
        assert captured["timeout"] == 180.0
