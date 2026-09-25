from dataclasses import dataclass, field

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


def resolve_llm_client_spec(settings: Settings) -> LLMClientSpec:
    """Resolve provider defaults and explicit settings into a pool key."""
    routing = resolve_llm_routing(settings)
    provider = routing.provider
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    api_mode = routing.api_mode
    if api_mode not in {"openai", "litellm"}:
        raise ValueError(f"Unsupported LLM API mode: {api_mode}")

    api_key = str(getattr(settings, "llm_api_key", "") or "").strip()
    if not api_key and defaults.get("api_key_required", True):
        label = str(defaults.get("label") or provider)
        raise LLMConfigurationError(
            f"{label} 缺少 API Key，请在设置页填写个人 API Key。"
            "自定义调用目标不能复用全局 Key；管理员可通过 LLM_API_KEY 配置全局 Key"
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
