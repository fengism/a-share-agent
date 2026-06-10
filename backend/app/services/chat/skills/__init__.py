from app.services.chat.skills.registry import registry
from app.services.chat.skills.stock_skills import register_stock_skills
from app.services.chat.skills.market_skills import register_market_skills
from app.services.chat.skills.composite_skills import register_composite_skills
from app.services.chat.skills.web_skills import register_web_skills

_skills_registered = False


def register_all_skills():
    """注册全部 chat skills；重复调用时保持幂等。"""
    global _skills_registered
    if _skills_registered:
        return
    register_stock_skills()
    register_market_skills()
    register_composite_skills()
    register_web_skills()
    _skills_registered = True


__all__ = ["registry", "register_all_skills"]
