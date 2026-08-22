"""Shared LLM configuration contracts."""


class LLMConfigurationError(ValueError):
    """The selected provider cannot be used with the effective configuration."""
