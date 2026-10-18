"""One immutable compatibility policy for a provider + endpoint + model route."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

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


def _endpoint_key(base_url: str) -> str:
    try:
        return normalize_llm_endpoint(base_url)
    except ValueError:
        return ""  # Invalid/credential-bearing URLs cannot match any configured profile.


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
    official_route = (
        bool(endpoint)
        and endpoint == _endpoint_key(str(defaults.get("base_url", "")))
        and api_mode == defaults.get("api_mode")
        and provider in _FULL_TOOL_PROVIDERS
    )
    capabilities = model_parameter_defaults(model)
    if not official_route:
        capabilities = replace(
            capabilities, streaming_tool_calls=False, parallel_tool_calls=False,
            supports_tool_choice_none=False, supports_tool_choice_required=False, supports_named_tool_choice=False,
        )
    # Official DeepSeek thinking defaults documented for these exact model IDs.
    # Mutable/unknown aliases are deliberately not assigned invented token limits.
    if official_route and provider == "deepseek" and model in {"deepseek-flash", "deepseek-v4-pro"}:
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
