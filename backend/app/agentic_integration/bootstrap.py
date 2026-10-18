import threading

from app.agentic.catalog import registry
from app.agentic_integration.agents.catalog import list_agent_profiles
from app.agentic_integration.skills.catalog import register_skill_catalog
from app.agentic_integration.tools.registration import register_all_tools

_capabilities_registered = False
_capabilities_lock = threading.Lock()


def register_all_capabilities() -> None:
    """Register tools, skills and profiles exactly once, with rollback on failure.

    ``GET /chat/capabilities`` runs in a thread pool, so the check-then-register
    sequence needs a lock just like tool registration. If profile validation
    fails after skills were added, remove those skills so a later retry does not
    hit "already registered" and become permanently stuck.
    """
    global _capabilities_registered
    if _capabilities_registered:
        return
    with _capabilities_lock:
        if _capabilities_registered:
            return
        before_skills = registry.skill_names()
        try:
            register_all_tools()
            register_skill_catalog()
            registered_tools = registry.tool_names()
            registered_skills = registry.skill_names()
            for profile in list_agent_profiles():
                missing_tools = sorted(set(profile.tool_names) - registered_tools)
                if missing_tools:
                    raise ValueError(f"Agent '{profile.name}' 引用了未注册工具：{missing_tools}")
                missing_skills = sorted(set(profile.skill_names) - registered_skills)
                if missing_skills:
                    raise ValueError(f"Agent '{profile.name}' 引用了未注册 Skill：{missing_skills}")
        except Exception:
            registry.unregister_skills(registry.skill_names() - before_skills)
            raise
        _capabilities_registered = True


__all__ = ["register_all_capabilities", "registry"]
