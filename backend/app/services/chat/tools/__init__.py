from app.services.chat.tools.stock_tools import register_stock_tools
from app.services.chat.tools.market_tools import register_market_tools
from app.services.chat.tools.composite_tools import register_composite_tools
from app.services.chat.tools.web_tools import register_web_tools

_tools_registered = False


def register_all_tools():
    """注册全部 chat tools；重复调用时保持幂等。"""
    global _tools_registered
    if _tools_registered:
        return
    register_stock_tools()
    register_market_tools()
    register_composite_tools()
    register_web_tools()
    _tools_registered = True


__all__ = ["register_all_tools"]
