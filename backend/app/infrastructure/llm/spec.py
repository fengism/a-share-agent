from dataclasses import dataclass, field
from typing import cast

from app.configuration.llm_routing import resolve_llm_routing
from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.schema import Settings
from app.domain.llm import LLMConfigurationError
from app.infrastructure.llm.capabilities import LLMCapabilities, capabilities_for_settings, resolve_llm_capabilities


@dataclass(frozen=True)
class LLMClientSpec:
    provider: str
    api_mode: str
    api_key: str = field(repr=False)
    base_url: str = field(repr=False)
    model: str
    api_version: str
    timeout: float
    capabilities: LLMCapabilities | None = None

    @property
    def effective_capabilities(self) -> LLMCapabilities:
        return self.capabilities or resolve_llm_capabilities(
            provider=self.provider, api_mode=self.api_mode, model=self.model,
            base_url=self.base_url, api_version=self.api_version,
        )

    @property
    def key(self) -> tuple[str, str, str, str, str, str, float, LLMCapabilities]:
        return (
            self.provider,
            self.api_mode,
            self.api_key,
            self.base_url,
            self.model,
            self.api_version,
            self.timeout,
            self.effective_capabilities,
        )


def simple_task_enabled(settings: Settings, task: str) -> bool:
    """该任务是否应使用子模型：需配置 ``llm_sub_model``，且任务在启用清单内（清单为空=全部）。"""
    if not settings.llm_sub_model.strip():
        return False
    configured = {
        item.strip()
        for item in settings.llm_simple_tasks.split(",")
        if item.strip()
    }
    return not configured or task in configured


def apply_task_model(settings: Settings, *, simple: bool = False, task: str | None = None) -> Settings:
    """简单/高频任务改用子模型：仅在配置了 ``llm_sub_model`` 时替换 model。

    仅替换 model（provider/base_url/api_key 不变），因此凭证隔离与连接池键
    （键含 model）都能自然生效，无需改动路由/流式链路。
    ``task`` 按 ``llm_simple_tasks`` 白名单判定；``simple`` 用于显式强制。
    """
    if not (simple or (task is not None and simple_task_enabled(settings, task))):
        return settings
    sub_model = settings.llm_sub_model.strip()
    if not sub_model or sub_model == settings.llm_model:
        return settings
    return cast(Settings, settings.model_copy(update={"llm_model": sub_model}))


def task_uses_sub_model(settings: Settings, *, simple: bool = False, task: str | None = None) -> bool:
    """本次调用是否真的会切到子模型（用于失败后是否回退主模型）。"""
    return apply_task_model(settings, simple=simple, task=task) is not settings


def resolve_llm_client_spec(settings: Settings) -> LLMClientSpec:
    """Resolve provider defaults and explicit settings into a pool key."""
    routing = resolve_llm_routing(settings)
    provider = routing.provider
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    api_mode = routing.api_mode
    if api_mode not in {"openai", "litellm"}:
        raise ValueError(f"Unsupported LLM API mode: {api_mode}")

    api_key = str(getattr(settings, "llm_api_key", "") or "").strip()
    if not api_key:
        from app.configuration import get_settings
        api_key = str(getattr(get_settings(), "llm_api_key", "") or "").strip()
    if not api_key and defaults.get("api_key_required", True):
        label = str(defaults.get("label") or provider)
        raise LLMConfigurationError(
            f"{label} 缺少 API Key，请在设置页填写个人 API Key，或由管理员配置全局 Key"
        )
    if not api_key and not defaults.get("api_key_required", True):
        api_key = "local"
    return LLMClientSpec(
        provider=provider,
        api_mode=api_mode,
        api_key=api_key,
        base_url=routing.base_url,
        model=routing.model,
        api_version=routing.api_version,
        timeout=float(getattr(settings, "llm_timeout_seconds", 120.0)),
        capabilities=capabilities_for_settings(settings),
    )
