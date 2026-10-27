"""Provider 能力矩阵契约。

这一层是手维护的规则表（谁支持流式工具调用、谁能并跑工具、谁的 token 参数叫
``max_completion_tokens``），此前没有任何回归保护。本文件把当前决策固定下来：
官方通道 → 全能力；聚合/本地网关 → 降级但保留原生工具；Azure 按厂商域名认定
官方通道；DeepSeek 思考模型关闭 temperature 并回放 reasoning_content；
部署上限永远是硬上限；用户 override 只影响显式匹配的路由。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.configuration.llm_compatibility import (
    LLMCompatibilityOverride,
    validate_extra_body,
)
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.runtime import build_updated_settings
from app.configuration.schema import Settings
from app.domain.llm import LLMConfigurationError
from app.infrastructure.llm.adapters import merge_extra_body, prepare_completion_kwargs
from app.infrastructure.llm.capabilities import (
    apply_deployment_limits,
    resolve_llm_capabilities,
)
from app.infrastructure.llm.runtime import OpenAIAsyncClient
from app.infrastructure.llm.spec import resolve_llm_client_spec

_FULL_TOOL_FLAGS = (
    "native_tool_calling",
    "streaming_tool_calls",
    "parallel_tool_calls",
    "supports_tool_choice_none",
    "supports_tool_choice_required",
    "supports_named_tool_choice",
)


def _defaults_route(provider: str, model: str | None = None, base_url: str | None = None, **kwargs):
    defaults = PROVIDER_DEFAULTS[provider]
    return resolve_llm_capabilities(
        provider=provider,
        api_mode=str(defaults["api_mode"]),
        model=model or str(defaults["model"]),
        base_url=str(defaults["base_url"]) if base_url is None else base_url,
        api_version=str(defaults.get("api_version", "")),
        **kwargs,
    )


@pytest.mark.parametrize("provider", ["openai", "qwen", "zhipu", "moonshot", "claude", "gemini"])
def test_official_routes_keep_full_tool_capabilities(provider: str) -> None:
    capabilities = _defaults_route(provider)
    for flag in _FULL_TOOL_FLAGS:
        assert getattr(capabilities, flag) is True, f"{provider} 官方通道应保留 {flag}"


def test_azure_real_deployment_host_is_official_route() -> None:
    """Azure 目录地址是占位符，真实部署名必然不同；按厂商域名后缀认定官方通道。"""
    capabilities = _defaults_route("azure", "azure/gpt-4o", "https://my-resource.openai.azure.com")
    for flag in _FULL_TOOL_FLAGS:
        assert getattr(capabilities, flag) is True, f"Azure 官方通道应保留 {flag}"


@pytest.mark.parametrize(
    "base_url",
    [
        "https://evil.example.com",  # 非厂商域名
        "https://my-resource.openai.azure.com.evil.com",  # 后缀伪装
        "http://my-resource.openai.azure.com",  # 明文传输
        "https://api.openai.com/v1",  # 换了厂商
    ],
)
def test_azure_foreign_endpoints_are_not_official(base_url: str) -> None:
    capabilities = _defaults_route("azure", "azure/gpt-4o", base_url)
    assert capabilities.streaming_tool_calls is False
    assert capabilities.parallel_tool_calls is False
    assert capabilities.supports_tool_choice_none is False
    assert capabilities.supports_named_tool_choice is False


def test_azure_requires_official_api_mode() -> None:
    capabilities = resolve_llm_capabilities(
        provider="azure",
        api_mode="openai",
        model="azure/gpt-4o",
        base_url="https://my-resource.openai.azure.com",
        api_version="2024-10-21",
    )
    assert capabilities.streaming_tool_calls is False


@pytest.mark.parametrize(
    "model",
    [
        "deepseek-v4-flash",  # 目录默认值
        "deepseek-v4-pro",
        "deepseek-flash",
        "deepseek-reasoner",
        "deepseek/deepseek-reasoner",
        # 同一世代的小版本升级必须沿用思考特化，不能因为名字变了就静默失效
        "deepseek-v4",
        "deepseek-v4.1",
        "deepseek-v4.1-pro",
        "deepseek-v4.1-flash",
        "deepseek-v4.2",
        "deepseek/deepseek-v4.1",
        # v4 之后的世代同样视为思考模型世代（小版本、大版本都不该漏）
        "deepseek-v5",
        "deepseek-v5.2",
        "deepseek-v5.2-flash",
        "deepseek-v6",
        "deepseek-v10.3-pro",
    ],
)
def test_deepseek_thinking_models_disable_temperature_and_replay_reasoning(model: str) -> None:
    capabilities = _defaults_route("deepseek", model)
    assert capabilities.supports_temperature is False
    assert capabilities.replay_tool_reasoning is True
    assert capabilities.supports_tool_choice_required is False
    assert capabilities.supports_named_tool_choice is False


@pytest.mark.parametrize(
    "model",
    [
        "deepseek-chat",
        # 同世代但显式声明聊天/指令的模型不能被当成思考模型
        "deepseek-v4-chat",
        "deepseek-v4.1-instruct",
        "deepseek-v5-chat",
        # v3 及以前不是思考模型世代
        "deepseek-v3",
        "deepseek-v3.5",
    ],
)
def test_non_thinking_deepseek_models_keep_temperature(model: str) -> None:
    capabilities = _defaults_route("deepseek", model)
    assert capabilities.supports_temperature is True
    assert capabilities.replay_tool_reasoning is False
    assert capabilities.supports_tool_choice_required is True


def test_reasoning_model_switches_token_parameter() -> None:
    capabilities = _defaults_route("openai", "gpt-5-mini")
    assert capabilities.token_parameter == "max_completion_tokens"
    assert capabilities.supports_temperature is False


@pytest.mark.parametrize("provider", ["openrouter", "ollama", "siliconflow", "custom"])
def test_aggregator_gateways_downgrade_advanced_tool_flags(provider: str) -> None:
    capabilities = _defaults_route(provider)
    # 原生工具调用保留（这些网关普遍支持），但流式/并行/强指定一律关闭。
    assert capabilities.native_tool_calling is True
    assert capabilities.streaming_tool_calls is False
    assert capabilities.parallel_tool_calls is False
    assert capabilities.supports_tool_choice_none is False
    assert capabilities.supports_tool_choice_required is False
    assert capabilities.supports_named_tool_choice is False


def test_unknown_gateway_for_provider_is_not_official() -> None:
    capabilities = _defaults_route("openai", "gpt-4o", "https://my-proxy.example.com/v1")
    assert capabilities.streaming_tool_calls is False
    assert capabilities.parallel_tool_calls is False


def test_model_specific_override_wins_over_gateway_wide_rule() -> None:
    gateway_wide = LLMCompatibilityOverride(
        provider="openai",
        base_url="https://api.openai.com/v1",
        supports_strict_json_schema=False,
        parallel_tool_calls=False,
    )
    model_specific = LLMCompatibilityOverride(
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o",
        supports_strict_json_schema=True,
        parallel_tool_calls=True,
    )
    capabilities = _defaults_route("openai", "gpt-4o", overrides=[gateway_wide, model_specific])
    assert capabilities.supports_strict_json_schema is True
    assert capabilities.parallel_tool_calls is True

    other_model = _defaults_route("openai", "gpt-4o-mini", overrides=[gateway_wide, model_specific])
    assert other_model.supports_strict_json_schema is False
    assert other_model.parallel_tool_calls is False


def test_override_requires_exact_endpoint_match() -> None:
    unrelated = LLMCompatibilityOverride(
        provider="openai",
        base_url="https://other.example.com/v1",
        supports_strict_json_schema=True,
    )
    capabilities = _defaults_route("openai", "gpt-4o", overrides=[unrelated])
    assert capabilities.supports_strict_json_schema is False


def test_deployment_limits_are_hard_caps() -> None:
    capabilities = _defaults_route("openai", "gpt-4o")
    settings = Settings(
        llm_json_mode_enabled=False,
        llm_stream_include_usage=False,
        llm_model_max_completion_tokens=2048,
    )
    limited = apply_deployment_limits(capabilities, settings)
    assert limited.json_mode is False
    assert limited.stream_include_usage is False
    assert limited.max_completion_tokens == 2048


def test_prepare_kwargs_drops_temperature_for_thinking_model() -> None:
    capabilities = _defaults_route("deepseek", "deepseek-reasoner")
    prepared = prepare_completion_kwargs(
        {
            "model": "deepseek-reasoner",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.3,
            "max_tokens": 512,
        },
        capabilities,
        expected_model="deepseek-reasoner",
    )
    assert "temperature" not in prepared
    assert prepared["max_tokens"] == 512


def test_prepare_kwargs_keeps_vendor_extra_body() -> None:
    capabilities = _defaults_route("qwen")
    prepared = prepare_completion_kwargs(
        {
            "model": "qwen-plus",
            "messages": [],
            "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
        },
        capabilities,
        expected_model="qwen-plus",
    )
    assert prepared["extra_body"] == {"chat_template_kwargs": {"enable_thinking": True}}


def test_prepare_kwargs_rejects_governed_extra_body() -> None:
    capabilities = _defaults_route("qwen")
    with pytest.raises(LLMConfigurationError):
        prepare_completion_kwargs(
            {"model": "qwen-plus", "messages": [], "extra_body": {"model": "other"}},
            capabilities,
            expected_model="qwen-plus",
        )


def test_validate_extra_body_rejects_non_object_and_governed_fields() -> None:
    assert validate_extra_body({"thinking": {"type": "enabled"}}) == {"thinking": {"type": "enabled"}}
    assert validate_extra_body(None) == {}
    with pytest.raises(ValueError):
        validate_extra_body(["not", "an", "object"])
    with pytest.raises(ValueError):
        validate_extra_body({"temperature": 0.9})


def test_merge_extra_body_deep_merges_nested_objects() -> None:
    merged = merge_extra_body(
        {"chat_template_kwargs": {"enable_thinking": True, "keep": 1}, "top": "base"},
        {"chat_template_kwargs": {"enable_thinking": False}, "extra": "call"},
    )
    assert merged == {
        "chat_template_kwargs": {"enable_thinking": False, "keep": 1},
        "top": "base",
        "extra": "call",
    }
    assert merge_extra_body({}, None) is None


async def test_async_client_forwards_settings_extra_body() -> None:
    """settings.llm_extra_body 必须真的进入请求体，并与调用级扩展合并。"""

    class _Recorder:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def create(self, **kwargs):
            self.calls.append(kwargs)
            return "response"

    recorder = _Recorder()
    capabilities = _defaults_route("qwen")
    wrapper = OpenAIAsyncClient(
        SimpleNamespace(chat=SimpleNamespace(completions=recorder)),
        capabilities=capabilities,
        model="qwen-plus",
        extra_body={"chat_template_kwargs": {"enable_thinking": True}},
    )
    await wrapper.chat.completions.create(
        model="qwen-plus",
        messages=[],
        extra_body={"top_p": 0.5},
    )
    assert recorder.calls[0]["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": True},
        "top_p": 0.5,
    }


def test_client_spec_key_tracks_extra_body() -> None:
    base = Settings(llm_api_key="key", llm_model="qwen-plus", llm_provider="qwen")
    thinking = base.model_copy(
        update={"llm_extra_body": {"chat_template_kwargs": {"enable_thinking": True}}}
    )
    assert resolve_llm_client_spec(base).key != resolve_llm_client_spec(thinking).key
    assert resolve_llm_client_spec(thinking).extra_body == {
        "chat_template_kwargs": {"enable_thinking": True}
    }


def test_settings_reject_governed_extra_body() -> None:
    with pytest.raises(Exception):
        Settings(llm_extra_body={"messages": []})


def test_build_updated_settings_validates_nested_override_models() -> None:
    """model_copy/setattr 不校验，裸 dict 必须在这里转换成模型实例。"""
    updated = build_updated_settings(
        Settings(),
        {
            "llm_compatibility_overrides": [
                {"provider": "azure", "base_url": "https://my-resource.openai.azure.com"}
            ],
            "llm_max_attempts": 3,
        },
    )
    assert isinstance(updated.llm_compatibility_overrides[0], LLMCompatibilityOverride)
    assert updated.llm_max_attempts == 3


def test_build_updated_settings_ignores_unparsable_value() -> None:
    updated = build_updated_settings(Settings(), {"llm_max_attempts": "not-a-number"})
    assert updated.llm_max_attempts == Settings().llm_max_attempts


def test_stored_extra_body_round_trips_through_user_overlay() -> None:
    """user_config 里存的是 JSON 文本，必须能反序列化回 dict 并进入客户端规格。"""
    from app.configuration import CONFIG_VALUE_FIELDS, GLOBAL_SYNCED_KEYS, PRIVATE_USER_KEYS
    from app.configuration.effective import overlay_private

    for key in ("llm_extra_body", "llm_max_attempts", "llm_timeout_seconds", "llm_json_mode_enabled"):
        assert key in CONFIG_VALUE_FIELDS
        assert key in PRIVATE_USER_KEYS
        assert key in GLOBAL_SYNCED_KEYS, f"{key} 需同步到全局基线，否则常驻任务看不到"

    base = Settings(llm_provider="qwen", llm_model="qwen-plus", llm_api_key="key")
    effective = overlay_private(
        base,
        {"llm_extra_body": '{"chat_template_kwargs": {"enable_thinking": true}}'},
    )
    assert effective.llm_extra_body == {"chat_template_kwargs": {"enable_thinking": True}}
    assert resolve_llm_client_spec(effective).extra_body == {
        "chat_template_kwargs": {"enable_thinking": True}
    }
