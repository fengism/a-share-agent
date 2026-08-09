"""Agentic Tool Pack 的统一注册入口。"""

from app.agentic.tools.packs.composite.registration import register_composite_tools
from app.agentic.tools.packs.market.registration import register_market_tools
from app.agentic.tools.packs.stock.registration import register_stock_tools
from app.agentic.tools.packs.web.runtime import register_twitter_tools, register_web_tools

_tools_registered = False


def register_all_tools() -> None:
    """注册全部 Agentic Tool Pack，并保证重复调用幂等。"""
    global _tools_registered
    if _tools_registered:
        return

    register_stock_tools()
    register_market_tools()
    register_composite_tools()
    register_web_tools()
    register_twitter_tools()
    _tools_registered = True
