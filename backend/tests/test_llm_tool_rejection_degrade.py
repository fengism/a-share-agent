"""网关拒绝 tools 时的自动降级：判定、记忆、重试范围。

背景：``native_tool_calling`` 对所有 provider 默认为真，而"网关不支持 tools"的
400 既不属瞬时故障（不重试）、也不属可识别的重试类别，于是自建/中转网关每次
工具轮都直接失败。这里验证降级的四条安全约束：

1. 只认 400/422 + 窄义措辞，schema 类错误（我们自己写错）绝不降级；
2. 每个调用最多降级重试一次，且不占用瞬时故障重试预算；
3. 事实按 ``(provider, api_mode, base_url, model)`` 记忆，后续请求不再发 tools；
4. 已经吐出内容之后的失败不重放（避免重复计费/重复输出）。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.configuration.schema import Settings


class _StatusError(Exception):
    """模拟 openai/litellm 的状态码异常（带 status_code 属性）。"""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class _RejectingCompletions:
    """带 tools 就 400、不带就成功；记录每次请求的 kwargs。"""

    def __init__(self, message: str = "tools are not supported by this model", status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("tools"):
            raise _StatusError(f"Error code: {self.status_code} - {self.message}", self.status_code)
        return _completion_response()


class _AlwaysFailingCompletions:
    """无论是否带 tools 都失败，用于验证"没有 tools 就不该触发降级"。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        raise _StatusError(f"Error code: {self.status_code} - {self.message}", self.status_code)


def _completion_response():
    """必须是 SDK 对象形态：``validate_chat_completion_response`` 明确拒绝裸 dict。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content="ok", tool_calls=[]),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )


class _Client:
    def __init__(self, completions: object, capabilities=None) -> None:
        self.chat = type("_Chat", (), {"completions": completions})()
        if capabilities is not None:
            self.capabilities = capabilities


def _settings(**updates) -> Settings:
    base = Settings(llm_provider="custom", llm_model="local-model",
                    llm_base_url="http://localhost:8000/v1", llm_api_key="k")
    return base.model_copy(update=updates) if updates else base


@pytest.fixture(autouse=True)
def _clean_memory():
    from app.infrastructure.llm.tool_support import reset_tool_support

    reset_tool_support()
    yield
    reset_tool_support()


# ---------------------------------------------------------------- 判定器


def test_rejection_message_markers_are_narrow() -> None:
    from app.domain.llm import is_tool_rejection_message

    assert is_tool_rejection_message("Error code: 400 - tools are not supported by this model")
    assert is_tool_rejection_message("400 unsupported parameter: tools")
    assert is_tool_rejection_message("该模型不支持工具调用")
    # schema 类错误里也含 tools，但那是我们自己的参数定义问题，不能降级。
    assert not is_tool_rejection_message("tools.0.function.parameters is invalid")
    assert not is_tool_rejection_message("tools is required when tool_choice is set")
    assert not is_tool_rejection_message("messages is required")


@pytest.mark.parametrize("status_code", [401, 403, 429, 500])
def test_non_400_status_never_degrades(status_code: int) -> None:
    from app.domain.llm import looks_like_tools_unsupported

    error = _StatusError(f"code {status_code} - tools are not supported", status_code)
    assert looks_like_tools_unsupported(error) is False


def test_cause_chain_is_followed() -> None:
    from app.domain.llm import looks_like_tools_unsupported

    inner = _StatusError("tools are not supported", 400)
    wrapper = RuntimeError("provider call failed")
    wrapper.__cause__ = inner
    assert looks_like_tools_unsupported(wrapper) is True


# ---------------------------------------------------------------- 记忆


def test_memory_is_per_route_and_expires(monkeypatch) -> None:
    from app.infrastructure.llm import tool_support

    route = tool_support.route_key(
        provider="custom", api_mode="openai", base_url="http://localhost:8000/v1", model="m1"
    )
    other_model = tool_support.route_key(
        provider="custom", api_mode="openai", base_url="http://localhost:8000/v1", model="m2"
    )
    tool_support.mark_tools_unsupported(route, now=100.0)
    assert tool_support.tools_unsupported(route, now=101.0) is True
    assert tool_support.tools_unsupported(other_model, now=101.0) is False
    expiry = 100.0 + tool_support.TOOL_SUPPORT_TTL_SECONDS
    assert tool_support.tools_unsupported(route, now=expiry + 1) is False


def test_memory_changes_resolved_capabilities() -> None:
    from app.infrastructure.llm import tool_support
    from app.infrastructure.llm.spec import resolve_llm_client_spec

    settings = _settings()
    assert resolve_llm_client_spec(settings).effective_capabilities.native_tool_calling is True

    route = tool_support.route_key_for_settings(settings)
    tool_support.mark_tools_unsupported(route)

    capabilities = resolve_llm_client_spec(settings).effective_capabilities
    assert capabilities.native_tool_calling is False
    assert capabilities.streaming_tool_calls is False


def test_saving_llm_settings_clears_the_memory() -> None:
    from app.infrastructure.llm import tool_support
    from app.modules.settings.effects import apply_update_side_effects

    route = tool_support.route_key_for_settings(_settings())
    tool_support.mark_tools_unsupported(route)
    assert tool_support.tools_unsupported(route) is True

    apply_update_side_effects(_settings(llm_model="upgraded-model"), {"llm_model": "upgraded-model"})
    assert tool_support.tools_unsupported(route) is False


# ---------------------------------------------------------------- 非流式重试


@pytest.mark.asyncio
async def test_non_streaming_retries_without_tools_once(monkeypatch) -> None:
    from app.infrastructure.llm import completion as completion_module

    completions = _RejectingCompletions()
    monkeypatch.setattr(completion_module, "call_settings", lambda: _settings())

    response = await completion_module.create_chat_completion(
        _Client(completions), messages=[{"role": "user", "content": "hi"}],
        model="local-model", tools=[{"type": "function", "function": {"name": "t"}}],
        tool_choice="auto", parallel_tool_calls=True,
    )

    assert response.choices[0].message.content == "ok"
    assert len(completions.calls) == 2
    # 第二次请求确实摘掉了全部工具相关参数
    for key in ("tools", "tool_choice", "parallel_tool_calls"):
        assert key not in completions.calls[1]
    # 记忆生效：同路由下一次调用不再带 tools
    from app.infrastructure.llm import tool_support

    assert tool_support.tools_unsupported(tool_support.route_key_for_settings(_settings())) is True


@pytest.mark.asyncio
async def test_schema_error_does_not_degrade_and_keeps_retry_semantics(monkeypatch) -> None:
    from app.infrastructure.llm import completion as completion_module

    completions = _RejectingCompletions(message="tools.0.function.parameters is invalid")
    monkeypatch.setattr(completion_module, "call_settings", lambda: _settings())

    with pytest.raises(Exception):
        await completion_module.create_chat_completion(
            _Client(completions), messages=[{"role": "user", "content": "hi"}],
            model="local-model", tools=[{"type": "function", "function": {"name": "t"}}],
        )

    assert len(completions.calls) == 1  # 非瞬时错误不重试，也没有摘工具
    from app.infrastructure.llm import tool_support

    assert tool_support.tools_unsupported(tool_support.route_key_for_settings(_settings())) is False


@pytest.mark.asyncio
async def test_request_without_tools_is_never_degraded(monkeypatch) -> None:
    from app.infrastructure.llm import completion as completion_module

    completions = _AlwaysFailingCompletions(message="tools are not supported")
    monkeypatch.setattr(completion_module, "call_settings", lambda: _settings())

    with pytest.raises(Exception):
        await completion_module.create_chat_completion(
            _Client(completions), messages=[{"role": "user", "content": "hi"}], model="local-model",
        )

    assert len(completions.calls) == 1


# ---------------------------------------------------------------- 流式重试


class _StreamingRejectingCompletions(_RejectingCompletions):
    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("tools"):
            raise _StatusError("Error code: 400 - tools are not supported by this model", 400)

        async def _gen():
            yield {"choices": [{"delta": {"content": "ok"}, "finish_reason": None}]}
            yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}

        return _gen()


@pytest.mark.asyncio
async def test_streaming_degrades_before_first_chunk(monkeypatch) -> None:
    from app.infrastructure.llm import completion as completion_module

    completions = _StreamingRejectingCompletions()
    monkeypatch.setattr(completion_module, "call_settings", lambda: _settings())

    chunks = [
        chunk
        async for chunk in completion_module.stream_chat_completion(
            _Client(completions), messages=[{"role": "user", "content": "hi"}],
            model="local-model", tools=[{"type": "function", "function": {"name": "t"}}],
        )
    ]

    assert chunks
    assert len(completions.calls) == 2
    assert "tools" not in completions.calls[1]


class _MidStreamRejectingCompletions:
    """首块之后才"报 400"：绝不重放，否则会重复计费/重复输出。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)

        async def _gen():
            yield {"choices": [{"delta": {"content": "部分输出"}, "finish_reason": None}]}
            raise _StatusError("Error code: 400 - tools are not supported", 400)

        return _gen()


@pytest.mark.asyncio
async def test_streaming_does_not_replay_after_first_chunk(monkeypatch) -> None:
    from app.infrastructure.llm import completion as completion_module

    completions = _MidStreamRejectingCompletions()
    monkeypatch.setattr(completion_module, "call_settings", lambda: _settings())

    received: list[object] = []
    with pytest.raises(Exception):
        async for chunk in completion_module.stream_chat_completion(
            _Client(completions), messages=[{"role": "user", "content": "hi"}],
            model="local-model", tools=[{"type": "function", "function": {"name": "t"}}],
        ):
            received.append(chunk)

    assert received  # 已经推进去的内容不能被撤回
    assert len(completions.calls) == 1  # 也不允许重放


def test_degraded_route_makes_agent_layer_send_no_tools() -> None:
    """记忆生效后，Agent 核心的工具请求整形必须真的不再带工具（而非只改标志位）。"""
    from app.domain.agent_llm import resolve_tool_request
    from app.infrastructure.llm import tool_support
    from app.infrastructure.llm.spec import resolve_llm_client_spec

    settings = _settings()
    tool_definitions = [{
        "type": "function",
        "function": {"name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}},
    }]
    healthy = resolve_llm_client_spec(settings).effective_capabilities
    assert resolve_tool_request(tool_definitions, "auto", stream=True, capabilities=healthy).tools

    tool_support.mark_tools_unsupported(tool_support.route_key_for_settings(settings))
    degraded = resolve_llm_client_spec(settings).effective_capabilities

    request = resolve_tool_request(tool_definitions, "auto", stream=True, capabilities=degraded)
    assert request.tools == ()
    assert request.tool_choice is None
