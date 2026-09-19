from dataclasses import dataclass

from app.configuration.provider_catalog import PROVIDER_DEFAULTS
from app.configuration.schema import Settings


@dataclass(frozen=True)
class LLMRouting:
    provider: str
    api_mode: str
    base_url: str
    model: str
    api_version: str

    @property
    def credential_scope(self) -> tuple[str, str, str, str, str]:
        # Full URLs are intentional: paths/queries can select different proxy tenants.
        # LiteLLM also routes by model; OpenAI-compatible models are only payload data.
        return (
            self.provider,
            self.api_mode,
            self.base_url,
            self.api_version,
            self.model if self.api_mode == "litellm" else "",
        )


def resolve_llm_routing(settings: Settings) -> LLMRouting:
    """Share routing defaults between credential isolation and client construction."""
    provider = str(getattr(settings, "llm_provider", "openai") or "openai").lower()
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    configured_mode = str(getattr(settings, "llm_api_mode", "auto") or "auto").lower()
    return LLMRouting(
        provider=provider,
        api_mode=str(defaults.get("api_mode", "openai")) if configured_mode == "auto" else configured_mode,
        base_url=str(getattr(settings, "llm_base_url", "") or defaults["base_url"]),
        model=str(getattr(settings, "llm_model", "") or defaults["model"]),
        api_version=str(getattr(settings, "llm_api_version", "") or defaults.get("api_version", "")),
    )
