"""One immutable compatibility policy for a provider + endpoint + model route."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from app.configuration.llm_compatibility import LLMCompatibilityOverride, normalize_llm_endpoint
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.domain.llm import (
    DEFAULT_LLM_CAPABILITIES as DEFAULT_LLM_CAPABILITIES,
)
from app.domain.llm import (
    LLMCapabilities as LLMCapabilities,
)
from app.domain.llm import (
    is_reasoning_model as is_reasoning_model,
)
from app.domain.llm import (
    model_parameter_defaults as model_parameter_defaults,
)

if TYPE_CHECKING:
    from app.configuration.schema import Settings

_FULL_TOOL_PROVIDERS = frozenset({"openai", "azure", "claude", "gemini", "deepseek", "qwen", "zhipu", "moonshot"})

#: Azure 的目录地址是占位符（``YOUR-RESOURCE``），真实部署名必然不同，
#: 因此只能按厂商域名后缀认定官方通道，而不是比较完整地址。除全球版，还要覆盖
#: 中国区（``.azure.cn``）与新版 AI Services / 经典 Cognitive Services 端点。
_AZURE_ENDPOINT_SUFFIXES = (
    ".openai.azure.com",
    ".openai.azure.cn",
    ".services.ai.azure.com",
    ".cognitiveservices.azure.com",
)

#: 官方 DeepSeek 思考模型：必须关闭 temperature 并回放 reasoning_content。
#:
#: 按**世代**匹配而不是精确枚举：v4 及以后的世代（v4、v4.1、v5、v5.2…）思考特化
#: 一致，小版本升级不该让适配静默失效。v3 及以前保持普通行为；同世代里显式声明
#: ``-chat``/``-instruct`` 的模型也保持普通行为。
_DEEPSEEK_THINKING_ALIASES = frozenset({
    "deepseek-flash",     # 早期思考模型别名
    "deepseek-reasoner",  # 公开 API 里的推理模型名
})
_DEEPSEEK_THINKING_GENERATION = re.compile(
    r"^deepseek-v(?P<major>\d+)(?:\.\d+)*(?:-[a-z0-9]+(?:\.[0-9]+)?)*$"
)
#: 世代门槛：v4 起视为思考模型世代（v3 及以前是非思考模型）。
_DEEPSEEK_THINKING_MIN_MAJOR = 4
_DEEPSEEK_NON_THINKING_TOKENS = frozenset({"chat", "instruct"})


def _is_deepseek_thinking_model(model_name: str) -> bool:
    """该 DeepSeek 模型是否属于思考模型世代。

    ``deepseek-v4``、``deepseek-v4.1-pro``、``deepseek-v5``、``deepseek-v5.2-flash``
    一律走思考特化；``deepseek-v3``/``deepseek-v3.5`` 与 ``deepseek-v4.1-chat`` 这类
    显式聊天模型保持普通行为（否则会静默丢掉 temperature 并往消息里塞
    reasoning_content）。若未来出现非思考的新世代，把其标记加进
    ``_DEEPSEEK_NON_THINKING_TOKENS`` 或在该世代名上显式排除即可。
    """
    name = model_name.strip().lower()
    if name in _DEEPSEEK_THINKING_ALIASES:
        return True
    match = _DEEPSEEK_THINKING_GENERATION.match(name)
    if match is None:
        return False
    if int(match.group("major")) < _DEEPSEEK_THINKING_MIN_MAJOR:
        return False
    suffix = name[len("deepseek-"):]
    return not any(token in _DEEPSEEK_NON_THINKING_TOKENS for token in suffix.split("-"))


def _endpoint_key(base_url: str) -> str:
    try:
        return normalize_llm_endpoint(base_url)
    except ValueError:
        return ""  # Invalid/credential-bearing URLs cannot match any configured profile.


def _endpoint_host(endpoint: str) -> str:
    """已归一化的地址取 host；解析失败视为不匹配而不是抛错。"""
    try:
        return urlsplit(endpoint).hostname or ""
    except ValueError:
        return ""


def _is_official_route(
    provider: str, endpoint: str, api_mode: str, defaults: Mapping[str, Any],
) -> bool:
    """是否为该 provider 的官方（未经自定义网关改写）通道。

    只有官方通道才开启流式工具调用/并行工具/强制 tool_choice 等高级能力：
    这些字段一旦被中转网关忽略，请求会静默降级或直接 400。
    """
    if not endpoint or provider not in _FULL_TOOL_PROVIDERS:
        return False
    if api_mode != defaults.get("api_mode"):
        return False
    if provider == "azure":
        host = _endpoint_host(endpoint)
        return endpoint.startswith("https://") and host.endswith(_AZURE_ENDPOINT_SUFFIXES)
    return endpoint == _endpoint_key(str(defaults.get("base_url", "")))


def resolve_llm_capabilities(
    *, provider: str, api_mode: str, model: str, base_url: str = "", api_version: str = "",
    overrides: tuple[LLMCompatibilityOverride, ...] | list[LLMCompatibilityOverride] = (),
) -> LLMCapabilities:
    """Defaults -> gateway rules -> model rules. Later ties win, never reroute.

    Optional request fields keep their legacy defaults for unknown gateways;
    advanced tool capabilities require an official route or an explicit rule.
    No model token capacities are guessed from names or mutable aliases.
    """
    provider = provider.strip().lower()
    endpoint = _endpoint_key(base_url)
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    official_route = _is_official_route(provider, endpoint, api_mode, defaults)
    capabilities = model_parameter_defaults(model)
    if not official_route:
        capabilities = replace(
            capabilities, streaming_tool_calls=False, parallel_tool_calls=False,
            supports_tool_choice_none=False, supports_tool_choice_required=False, supports_named_tool_choice=False,
        )
    # Official DeepSeek thinking defaults documented for these exact model IDs.
    # Mutable/unknown aliases are deliberately not assigned invented token limits.
    model_name = model.rsplit("/", 1)[-1].strip().lower()
    if official_route and provider == "deepseek" and _is_deepseek_thinking_model(model_name):
        capabilities = replace(
            capabilities, supports_temperature=False, supports_tool_choice_required=False,
            supports_named_tool_choice=False, replay_tool_reasoning=True,
        )
    matching = [
        rule for rule in overrides
        if rule.provider == provider and endpoint and rule.base_url == endpoint
        and (rule.model is None or rule.model == model)
        and (rule.api_mode is None or rule.api_mode == api_mode)
        and (rule.api_version is None or rule.api_version == api_version)
    ]
    # Stable sort: model-specific > gateway-wide, then mode/version specificity.
    matching.sort(key=lambda rule: (rule.model is not None, (rule.api_mode is not None) + (rule.api_version is not None)))
    selectors = {"provider", "base_url", "api_mode", "model", "api_version"}
    for rule in matching:
        capabilities = replace(capabilities, **rule.model_dump(exclude=selectors, exclude_none=True))
    if not capabilities.native_tool_calling:
        capabilities = replace(
            capabilities, streaming_tool_calls=False, parallel_tool_calls=False,
            supports_tool_choice_none=False, supports_tool_choice_required=False, supports_named_tool_choice=False,
        )
    return capabilities


def apply_deployment_limits(capabilities: LLMCapabilities, settings: Settings) -> LLMCapabilities:
    """Deployment switches/cap are hard limits, not model capability claims."""
    caps = [cap for cap in (capabilities.max_completion_tokens, settings.llm_model_max_completion_tokens) if cap is not None]
    return replace(
        capabilities,
        json_mode=capabilities.json_mode and settings.llm_json_mode_enabled,
        stream_include_usage=capabilities.stream_include_usage and settings.llm_stream_include_usage,
        max_completion_tokens=min(caps) if caps else None,
    )


def capabilities_for_settings(settings: Settings, *, model: str | None = None) -> LLMCapabilities:
    from app.configuration.llm_routing import resolve_llm_routing

    routing = resolve_llm_routing(settings)
    return apply_deployment_limits(resolve_llm_capabilities(
        provider=routing.provider, api_mode=routing.api_mode, base_url=routing.base_url,
        model=routing.model if model is None else model, api_version=routing.api_version,
        overrides=settings.llm_compatibility_overrides,
    ), settings)
