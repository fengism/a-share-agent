from __future__ import annotations

from collections.abc import Collection

from app.agentic.agents.contracts import AgentProfile
from app.agentic_integration.agents.profiles.fundamental import PROFILE as FUNDAMENTAL_PROFILE
from app.agentic_integration.agents.profiles.macro import PROFILE as MACRO_PROFILE
from app.agentic_integration.agents.profiles.news import PROFILE as NEWS_PROFILE
from app.agentic_integration.agents.profiles.risk import PROFILE as RISK_PROFILE
from app.agentic_integration.agents.profiles.technical import PROFILE as TECHNICAL_PROFILE

_PROFILES = (
    TECHNICAL_PROFILE,
    FUNDAMENTAL_PROFILE,
    NEWS_PROFILE,
    RISK_PROFILE,
    MACRO_PROFILE,
)


def list_agent_profiles() -> list[AgentProfile]:
    return list(_PROFILES)


def select_agent_profiles(
    names: Collection[str] | None = None,
) -> dict[str, AgentProfile]:
    selected = None if names is None else set(names)
    return {
        profile.name: profile
        for profile in _PROFILES
        if selected is None or profile.name in selected
    }
