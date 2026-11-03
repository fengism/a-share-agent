"""备用模型降级（llm_fallback_model）的行为契约。

关键约定：
* 降级必须换掉 **客户端**，而不是只改 ``model`` 字段——SDK 封装层会校验
  「请求模型 == 客户端模型」，只改 kwargs 必然抛 LLMConfigurationError。
* 只有账号级额度/限流与上游 5xx 才降级；400/401/403/404 等一律不降级。
"""

from __future__ import annotations

import httpx
import pytest
from openai import APIStatusError

from app.configuration.schema import Settings
from app.domain.llm import LLMCapabilities, LLMConfigurationError, LLMRetryableError
from app.infrastructure.llm.completion import (
    _apply_fallback_model_if_available,
    _compute_retry_delay,
    _is_fallback_eligible,
    _is_quota_or_rate_limit,
    create_chat_completion,
    stream_chat_completion,
)
from app.infrastructure.llm.runtime import create_async_openai_chat_runtime


def _settings(**kwargs) -> Settings:
    defaults = {
        "llm_provider": "openai",
        "llm_api_mode": "openai",
        "llm_base_url": "https://api.example.com/v1",
        "llm_api_key": "sk-test",
        "llm_model": "main-model",
        "llm_fallback_model": "fallback-model",
        "llm_max_attempts": 2,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


class DummyError(Exception):
    def __init__(self, msg: str, status_code: int | None = None) -> None:
        super().__init__(msg)
        self.status_code = status_code


def _api_status_error(status_code: int, message: str) -> APIStatusError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(status_code, request=request, json={"error": {"message": message}})
    return APIStatusError(message, response=response, body=None)


# --- 判定函数 -------------------------------------------------------------


def test_is_quota_or_rate_limit():
    assert _is_quota_or_rate_limit(DummyError("rate limit exceeded", status_code=429))
    assert _is_quota_or_rate_limit(DummyError("insufficient_quota"))
    assert _is_quota_or_rate_limit(DummyError("Too Many Requests"))
    assert _is_quota_or_rate_limit(DummyError("余额不足", status_code=402))
    assert not _is_quota_or_rate_limit(DummyError("internal server error", status_code=500))
    assert not _is_quota_or_rate_limit(DummyError("connection reset by peer"))


def test_numeric_message_is_not_mistaken_for_rate_limit():
    """上游 400 消息里的数字不得被当成 429（曾用裸子串 ``"429"`` 匹配）。"""
    assert not _is_quota_or_rate_limit(DummyError("max_tokens 14290 exceeds the limit", status_code=400))
    assert _compute_retry_delay(DummyError("max_tokens 14290 exceeds", status_code=400), 1) == pytest.approx(0.25)


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_client_errors_are_not_fallback_eligible(status_code: int):
    error = _api_status_error(status_code, "some upstream message")
    assert not _is_fallback_eligible(error, normalized=error)


@pytest.mark.parametrize("status_code", [429, 402, 500, 502, 503])
def test_account_and_upstream_errors_are_fallback_eligible(status_code: int):
    error = _api_status_error(status_code, "upstream detail")
    assert _is_fallback_eligible(error, normalized=error)


# --- _apply_fallback_model_if_available -----------------------------------


def _fake_factory(built: list[str]):
    async def factory(model: str) -> object:
        built.append(model)
        return object()

    return factory


async def test_apply_fallback_model_not_configured():
    settings = _settings(llm_fallback_model="")
    kwargs = {"model": "main-model"}
    built: list[str] = []
    result = await _apply_fallback_model_if_available(
        DummyError("quota exceeded", status_code=429), kwargs,
        settings=settings, metric_stage="test", transient_attempt=1,
        fallback_client_factory=_fake_factory(built),
    )
    assert result is None
    assert kwargs["model"] == "main-model"
    assert built == []


async def test_apply_fallback_model_already_on_fallback(caplog):
    """简单任务切到 llm_sub_model 且恰好等于 fallback 时，不能死循环，要告警。"""
    settings = _settings(llm_sub_model="fallback-model", llm_fallback_model="fallback-model")
    kwargs = {"model": "fallback-model"}
    with caplog.at_level("WARNING"):
        result = await _apply_fallback_model_if_available(
            DummyError("quota exceeded", status_code=429), kwargs,
            settings=settings, metric_stage="test", transient_attempt=1,
            fallback_client_factory=_fake_factory([]),
        )
    assert result is None
    assert kwargs["model"] == "fallback-model"
    assert "备用模型与当前模型相同" in caplog.text


async def test_apply_fallback_model_on_429_builds_new_client():
    settings = _settings()
    kwargs = {"model": "main-model", "temperature": 0.5}
    built: list[str] = []
    result = await _apply_fallback_model_if_available(
        DummyError("quota exceeded", status_code=429), kwargs,
        settings=settings, metric_stage="test", transient_attempt=1,
        fallback_client_factory=_fake_factory(built),
    )
    assert result is not None
    assert kwargs["model"] == "fallback-model"
    assert built == ["fallback-model"]


async def test_apply_fallback_model_requires_factory():
    """没有工厂时不得只改 model 字段，否则降级请求必然被 expected_model 拒绝。"""
    settings = _settings()
    kwargs = {"model": "main-model"}
    result = await _apply_fallback_model_if_available(
        DummyError("quota exceeded", status_code=429), kwargs,
        settings=settings, metric_stage="test", transient_attempt=1,
    )
    assert result is None
    assert kwargs["model"] == "main-model"


async def test_apply_fallback_model_waits_for_retry_budget_on_5xx():
    """上游 5xx 属于瞬时故障：先用完重试预算，再降级。"""
    settings = _settings(llm_max_attempts=2)
    error = _api_status_error(503, "server busy")
    kwargs = {"model": "main-model"}
    built: list[str] = []
    assert await _apply_fallback_model_if_available(
        error, kwargs, settings=settings, metric_stage="test", transient_attempt=1,
        fallback_client_factory=_fake_factory(built),
    ) is None
    assert built == []
    assert await _apply_fallback_model_if_available(
        error, kwargs, settings=settings, metric_stage="test", transient_attempt=2,
        fallback_client_factory=_fake_factory(built),
    ) is not None
    assert built == ["fallback-model"]


async def test_apply_fallback_model_skipped_when_factory_fails():
    """备用模型自身配置非法时放弃降级，保留原始错误。"""
    settings = _settings()
    kwargs = {"model": "main-model"}

    async def broken_factory(model: str) -> object:
        raise LLMConfigurationError("备用模型不可用")

    assert await _apply_fallback_model_if_available(
        DummyError("quota exceeded", status_code=429), kwargs,
        settings=settings, metric_stage="test", transient_attempt=1,
        fallback_client_factory=broken_factory,
    ) is None
    assert kwargs["model"] == "main-model"


# --- 真实 SDK 封装路径（此前的测试盲区） ----------------------------------


@pytest.mark.asyncio
async def test_real_runtime_fallback_client_rejects_foreign_model():
    """回归防线：证明「只换 model 字段」在真实封装层必然失败。"""
    settings = _settings()
    runtime = create_async_openai_chat_runtime(settings, max_retries=0)
    try:
        with pytest.raises(LLMConfigurationError):
            await runtime.client.chat.completions.create(model="fallback-model", messages=[])
    finally:
        await runtime.client.close()


@pytest.mark.asyncio
async def test_real_runtime_fallback_client_accepts_own_model():
    """按备用模型新建的客户端能通过 expected_model 校验（直接走到连接层，不发真实请求）。"""
    settings = _settings(llm_base_url="http://127.0.0.1:1/v1")
    runtime = create_async_openai_chat_runtime(
        settings.model_copy(update={"llm_model": "fallback-model"}), max_retries=0
    )
    try:
        assert getattr(runtime.client, "capabilities", None) is not None
        # 不再抛配置错误：请求已通过整形，失败只会来自网络/凭据层。
        with pytest.raises(Exception) as excinfo:
            await runtime.client.chat.completions.create(model="fallback-model", messages=[], timeout=0.5)
        assert not isinstance(excinfo.value, LLMConfigurationError)
    finally:
        await runtime.client.close()


# --- 端到端：非流式 -------------------------------------------------------


def _patch_pool(monkeypatch, fallback_client, built: list[str] | None = None):
    """替换池化借用入口：真实路径经 borrow_async_openai_chat_runtime 取客户端。

    降级后 ``_prepare_request`` 会用 ``client.capabilities`` 重新整形，所以这里必须
    按备用模型的真实 settings 派生能力位（而不是重复用入参 client 的旧能力位），
    否则“备用模型不支持 tools”这类兼容性用例会被 fake 掩掉。
    """
    import contextlib

    from app.infrastructure.llm import runtime as runtime_module
    from app.infrastructure.llm.capabilities import capabilities_for_settings

    @contextlib.asynccontextmanager
    async def borrow(settings=None, **_kwargs):
        if built is not None:
            built.append(settings.llm_model)
        fallback_client.capabilities = capabilities_for_settings(settings)
        yield runtime_module.AsyncOpenAIChatRuntime(
            client=fallback_client,
            model=settings.llm_model,
            capabilities=capabilities_for_settings(settings),
        )

    monkeypatch.setattr(runtime_module, "borrow_async_openai_chat_runtime", borrow)


class _RecordingClient:
    """最小可用客户端替身：仅记录收到的 model，并按脚本抛错/返回。"""

    def __init__(self, model: str, script):
        self.model = model
        self.capabilities = LLMCapabilities()
        self.calls: list[str] = []
        self._script = script
        self.closed = False
        self.chat = type("Chat", (), {"completions": self})()

    async def create(self, **kwargs):
        self.calls.append(kwargs.get("model"))
        outcome = self._script.get(kwargs.get("model"))
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def close(self) -> None:
        self.closed = True


def _response(text: str):
    from types import SimpleNamespace

    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))], usage=None)


@pytest.mark.asyncio
async def test_create_chat_completion_falls_back_on_429(monkeypatch):
    settings = _settings()
    main = _RecordingClient("main-model", {"main-model": DummyError("quota exceeded", status_code=429)})
    fallback = _RecordingClient("fallback-model", {"fallback-model": _response("hello from fallback")})

    monkeypatch.setattr("app.infrastructure.llm.completion.call_settings", lambda: settings)
    _patch_pool(monkeypatch, fallback)

    response = await create_chat_completion(main, model="main-model")
    assert response.choices[0].message.content == "hello from fallback"
    assert main.calls == ["main-model"]
    assert fallback.calls == ["fallback-model"]


@pytest.mark.asyncio
async def test_create_chat_completion_does_not_fallback_on_401(monkeypatch):
    settings = _settings()
    error = _api_status_error(401, "invalid api key")
    main = _RecordingClient("main-model", {"main-model": error})
    built: list[str] = []

    monkeypatch.setattr("app.infrastructure.llm.completion.call_settings", lambda: settings)
    _patch_pool(monkeypatch, main, built)

    with pytest.raises(Exception):
        await create_chat_completion(main, model="main-model")
    assert built == [], "401 是凭证问题，换备用模型没有意义"


# --- 端到端：流式 ---------------------------------------------------------


class _Chunk:
    def __init__(self, content: str) -> None:
        self.choices = [type("C", (), {"delta": type("D", (), {"content": content})()})()]


async def _stream_once(content: str):
    yield _Chunk(content)


@pytest.mark.asyncio
async def test_stream_chat_completion_falls_back_on_429(monkeypatch):
    settings = _settings()
    main = _RecordingClient("main-model", {"main-model": DummyError("quota exceeded", status_code=429)})
    fallback = _RecordingClient("fallback-model", {"fallback-model": _stream_once("token")})

    monkeypatch.setattr("app.infrastructure.llm.completion.call_settings", lambda: settings)
    _patch_pool(monkeypatch, fallback)

    chunks = [c async for c in stream_chat_completion(main, model="main-model")]
    assert [c.choices[0].delta.content for c in chunks] == ["token"]
    assert main.calls == ["main-model"]
    assert fallback.calls == ["fallback-model"]


@pytest.mark.asyncio
async def test_stream_chat_completion_no_fallback_after_first_chunk(monkeypatch):
    """已经吐出内容后不得切换：会重复输出/重复计费。"""
    settings = _settings()
    error = DummyError("quota exceeded", status_code=429)

    class MidStreamClient(_RecordingClient):
        async def create(self, **kwargs):
            self.calls.append(kwargs.get("model"))

            async def gen():
                yield _Chunk("partial")
                raise error

            return gen()

    client = MidStreamClient("main-model", {})
    built: list[str] = []

    monkeypatch.setattr("app.infrastructure.llm.completion.call_settings", lambda: settings)
    _patch_pool(monkeypatch, client, built)

    seen: list[str] = []
    with pytest.raises(Exception):
        async for chunk in stream_chat_completion(client, model="main-model", request_timeout=0.5):
            seen.append(chunk.choices[0].delta.content)
    assert seen == ["partial"]
    assert built == []


# --- 降级后的请求整形 -----------------------------------------------------


def test_prepare_request_is_safe_to_reapply_after_fallback():
    """降级后要用新客户端重新整形请求，``prepare_completion_kwargs`` 必须幂等。

    主模型与备用模型可能属于不同的 token 参数族（gpt-4o 用 max_tokens，
    o3-mini 用 max_completion_tokens）。二次整形要迁移参数名并保住预算，
    既不能丢限额，也不能把两个参数同时发出去被网关拒绝。
    """
    from app.infrastructure.llm.capabilities import capabilities_for_settings
    from app.infrastructure.llm.completion import _prepare_request

    settings = _settings(chat_max_completion_tokens=1000, llm_model="gpt-4o")
    main_cap = capabilities_for_settings(settings, model="gpt-4o")
    fallback_cap = capabilities_for_settings(settings, model="o3-mini")

    class _Client:
        def __init__(self, capabilities):
            self.capabilities = capabilities

    first = _prepare_request(
        _Client(main_cap), {"model": "gpt-4o"}, settings=settings, max_completion_tokens=None,
    )
    assert first.get("max_tokens") == 1000

    first["model"] = "o3-mini"
    second = _prepare_request(
        _Client(fallback_cap), first, settings=settings, max_completion_tokens=None,
    )
    assert second.get("max_completion_tokens") == 1000
    assert second.get("max_tokens") is None, "两个 token 参数同时出现会被网关拒绝"


# --- 备用模型装不下原请求 -------------------------------------------------


def test_prepare_fallback_request_returns_none_when_fallback_lacks_tools():
    """备用模型不支持 tools 时必须放弃降级，不能抛 LLMConfigurationError 掩盖原始 429。"""
    from app.infrastructure.llm.capabilities import capabilities_for_settings
    from app.infrastructure.llm.completion import _prepare_fallback_request

    settings = _settings(
        llm_model="fallback-model",
        llm_compatibility_overrides=[
            {
                "provider": "openai",
                "base_url": "https://api.example.com/v1",
                "model": "fallback-model",
                "native_tool_calling": False,
            }
        ],
    )
    capabilities = capabilities_for_settings(settings)
    assert capabilities.native_tool_calling is False

    class _Client:
        def __init__(self, caps):
            self.capabilities = caps

    tools = [
        {"type": "function", "function": {"name": "f", "description": "d", "parameters": {"type": "object"}}}
    ]
    result = _prepare_fallback_request(
        _Client(capabilities),
        {"model": "fallback-model", "tools": tools, "tool_choice": "auto"},
        settings=settings,
        max_completion_tokens=None,
        metric_stage="test",
    )
    assert result is None


def test_prepare_fallback_request_keeps_request_when_fallback_supports_tools():
    from app.infrastructure.llm.capabilities import capabilities_for_settings
    from app.infrastructure.llm.completion import _prepare_fallback_request

    settings = _settings(llm_model="fallback-model")
    capabilities = capabilities_for_settings(settings)

    class _Client:
        def __init__(self, caps):
            self.capabilities = caps

    tools = [
        {"type": "function", "function": {"name": "f", "description": "d", "parameters": {"type": "object"}}}
    ]
    result = _prepare_fallback_request(
        _Client(capabilities),
        {"model": "fallback-model", "tools": tools},
        settings=settings,
        max_completion_tokens=None,
        metric_stage="test",
    )
    assert result is not None
    assert result.get("tools")


async def test_create_chat_completion_preserves_original_error_when_fallback_incompatible(monkeypatch):
    """端到端：备用模型不支持 tools 时，抛出的必须是原始限流错误而非配置错误。"""
    settings = _settings(
        llm_max_attempts=1,
        llm_compatibility_overrides=[
            {
                "provider": "openai",
                "base_url": "https://api.example.com/v1",
                "model": "fallback-model",
                "native_tool_calling": False,
            }
        ],
    )
    main = _RecordingClient("main-model", {"main-model": DummyError("rate limit exceeded", status_code=429)})
    built: list[str] = []

    monkeypatch.setattr("app.infrastructure.llm.completion.call_settings", lambda: settings)
    _patch_pool(monkeypatch, main, built)

    tools = [
        {"type": "function", "function": {"name": "f", "description": "d", "parameters": {"type": "object"}}}
    ]
    with pytest.raises(Exception) as excinfo:
        await create_chat_completion(
            main, model="main-model", messages=[{"role": "user", "content": "hi"}],
            tools=tools, tool_choice="auto",
        )
    assert not isinstance(excinfo.value, LLMConfigurationError), "原始限流错误不能被配置错误掩盖"
    assert isinstance(excinfo.value, LLMRetryableError), "应保留原始限流错误的可重试语义"


async def test_fallback_opportunity_is_not_retried_after_incompatible_reshape(monkeypatch):
    """整形失败后不得在后续重试里再租一次备用客户端（降级机会只有一次）。"""
    settings = _settings(
        llm_max_attempts=3,
        llm_compatibility_overrides=[
            {
                "provider": "openai",
                "base_url": "https://api.example.com/v1",
                "model": "fallback-model",
                "native_tool_calling": False,
            }
        ],
    )
    main = _RecordingClient(
        "main-model",
        {"main-model": DummyError("rate limit exceeded", status_code=429)},
    )
    built: list[str] = []

    monkeypatch.setattr("app.infrastructure.llm.completion.call_settings", lambda: settings)
    _patch_pool(monkeypatch, main, built)

    tools = [
        {"type": "function", "function": {"name": "f", "description": "d", "parameters": {"type": "object"}}}
    ]
    with pytest.raises(Exception):
        await create_chat_completion(
            main, model="main-model", messages=[{"role": "user", "content": "hi"}],
            tools=tools, tool_choice="auto",
        )
    assert built == ["fallback-model"], f"备用客户端只应租一次，实际 {built}"
