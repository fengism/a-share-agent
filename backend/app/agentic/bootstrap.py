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
    _capabilities_registered = True


__all__ = ["register_all_capabilities", "registry"]
