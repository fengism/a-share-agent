"""Settings port for the agent runtime.

Only the fields used by the core executor are declared. The host installs its
real settings provider at composition time; the core never imports app.configuration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class AgentSettings(Protocol):
    """Host-provided settings surface used by the core executor.

    Fields below are read through ``getattr`` where a standalone or extracted
    caller may legitimately omit them; declaring them here documents the real
    host contract without making them a hard import-time requirement.
    """
    chat_max_completion_tokens: int
    chat_max_tool_calls_per_round: int
    chat_max_tool_calls_total: int
    chat_max_tool_context_characters: int
    chat_max_history_characters: int
    chat_max_initial_tools: int
    chat_max_prompt_characters: int
    chat_tool_process_cache_enabled: bool
    chat_max_skill_loads_total: int
    chat_tool_timeout_seconds: float
    llm_context_length_tokens: int
    llm_generation_timeout_seconds: float


_default_settings_provider: Callable[[], AgentSettings] | None = None


def configure_default_settings(provider: Callable[[], AgentSettings]) -> None:
    global _default_settings_provider
    _default_settings_provider = provider


def get_default_settings() -> AgentSettings:
    if _default_settings_provider is None:
        raise RuntimeError(
            "Agentic 默认 Settings 尚未配置；请在组合根调用 "
            "app.agentic.runtime.settings.configure_default_settings()"
        )
    return _default_settings_provider()


__all__ = [
    "AgentSettings",
    "configure_default_settings",
    "get_default_settings",
]
