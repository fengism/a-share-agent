"""Agentic Tool Pack 的统一注册入口。"""

import threading

from app.agentic.catalog import registry
from app.agentic.tools.packs.composite.registration import register_composite_tools
from app.agentic.tools.packs.market.registration import register_market_tools
from app.agentic.tools.packs.quant.registration import register_quant_tools
from app.agentic.tools.packs.stock.registration import register_stock_tools
from app.agentic.tools.packs.web.runtime import register_twitter_tools, register_web_tools

_registration_lock = threading.Lock()
_tools_registered = False


def register_all_tools() -> None:
    """注册全部 Agentic Tool Pack，并保证重复调用幂等且失败后可重试。

    两处必须成立，缺一个都会留下长期故障：

    1. 门闩用锁而不是裸 ``global bool``。``GET /chat/capabilities`` 是同步端点，会被
       丢到线程池；两个线程同时通过检查就会同时注册，撞上「已注册，禁止静默覆盖」。
    2. 失败要回滚。中途抛异常时若把已注册的留在 registry 里，下次重跑会在第一个
       工具就撞上「已注册」，注册从此永久无法完成——只能重启进程，此后每次请求 500。
    """
    global _tools_registered
    if _tools_registered:
        return
    with _registration_lock:
        if _tools_registered:
            return
        before = set(registry._tools)
        try:
            register_stock_tools()
            register_market_tools()
            register_quant_tools()
            register_composite_tools()
            register_web_tools()
            register_twitter_tools()
        except Exception:
            for name in set(registry._tools) - before:
                registry._tools.pop(name, None)
            raise
        _tools_registered = True
