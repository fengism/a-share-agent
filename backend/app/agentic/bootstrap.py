from app.agentic.agents.catalog import list_agent_profiles
from app.agentic.catalog import registry
from app.agentic.skills.catalog import register_skill_catalog
from app.agentic.tools.registration import register_all_tools

_capabilities_registered = False


def register_all_capabilities() -> None:
    global _capabilities_registered
    if _capabilities_registered:
        return
    register_all_tools()
    register_skill_catalog()
    registered_tools = {tool.name for tool in registry.list_tools()}
    registered_skills = {skill.name for skill in registry.list_skills()}
    for profile in list_agent_profiles():
        missing_tools = sorted(set(profile.tool_names) - registered_tools)
        if missing_tools:
            raise ValueError(f"Agent '{profile.name}' 引用了未注册工具：{missing_tools}")
        missing_skills = sorted(set(profile.skill_names) - registered_skills)
        if missing_skills:
            raise ValueError(f"Agent '{profile.name}' 引用了未注册 Skill：{missing_skills}")
    _capabilities_registered = True


__all__ = ["register_all_capabilities", "registry"]
