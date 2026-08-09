from dataclasses import dataclass

from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.schema import Settings


@dataclass(frozen=True)
class LLMClientSpec:
    provider: str
    api_mode: str
    api_key: str
    base_url: str
    model: str
    api_version: str
    timeout: float

    @property
    def key(self) -> tuple[str, str, str, str, str, str, float]:
        return (
            self.provider,
            self.api_mode,
            self.api_key,
            self.base_url,
            self.model,
            self.api_version,
            self.timeout,
        )


def resolve_llm_client_spec(settings: Settings) -> LLMClientSpec:
    """Resolve provider defaults and explicit settings into a pool key."""
    provider = str(getattr(settings, "llm_provider", "openai") or "openai").lower()
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    configured_mode = str(getattr(settings, "llm_api_mode", "auto") or "auto").lower()
    api_mode = (
        str(defaults.get("api_mode", "openai"))
        if configured_mode == "auto"
        else configured_mode
    )
    if api_mode not in {"openai", "litellm"}:
        raise ValueError(f"Unsupported LLM API mode: {api_mode}")

    api_key = str(getattr(settings, "llm_api_key", "") or "")
    if not api_key and not defaults.get("api_key_required", True):
        api_key = "local"
    return LLMClientSpec(
        provider=provider,
        api_mode=api_mode,
        api_key=api_key,
        base_url=str(getattr(settings, "llm_base_url", "") or defaults["base_url"]),
        model=str(getattr(settings, "llm_model", "") or defaults["model"]),
        api_version=str(
            getattr(settings, "llm_api_version", "") or defaults.get("api_version", "")
        ),
        timeout=float(getattr(settings, "llm_timeout_seconds", 120.0)),
    )
