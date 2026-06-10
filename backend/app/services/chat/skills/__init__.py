from app.services.chat.tools.registry import registry
from app.services.chat.skills.skill_catalog import register_skill_catalog
from app.services.chat.tools import register_all_tools

_skills_registered = False


def register_all_skills():
    """注册全部 chat tools 和 skills；重复调用时保持幂等。"""
    global _skills_registered
    if _skills_registered:
        return
    register_all_tools()
    register_skill_catalog()
    _skills_registered = True


__all__ = ["registry", "register_all_skills"]
