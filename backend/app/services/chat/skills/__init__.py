from app.services.chat.skills.registry import registry
from app.services.chat.skills.stock_skills import register_stock_skills
from app.services.chat.skills.market_skills import register_market_skills
from app.services.chat.skills.composite_skills import register_composite_skills


def register_all_skills():
    register_stock_skills()
    register_market_skills()
    register_composite_skills()


__all__ = ["registry", "register_all_skills"]
