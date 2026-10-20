"""市场时间基准（domain 层权威定义）。

沪深 A 股行情、交易日历、复盘日期与港股行情对齐都统一使用 ``Asia/Shanghai``。

**为什么放在 domain**：该常量此前有三份实现（``app/core/timezones.py``、
``app/agentic/runtime/timezones.py``、``app/domain/industry_chain.py`` 经由
``app.core.market`` 间接使用），而 domain 是最底层，核心包与宿主都可以依赖它。
``app.core.timezones`` / ``app.agentic.runtime.timezones`` 现在只是转发，避免
直接改动 20+ 处既有 import。若哪天有人改错其中一份，跨模块日期口径就会不一致，
而且很难排查。

本模块刻意**不依赖 pandas 等重型依赖**，因此任何层次都可以安全导入——这也是它没有
放在 :mod:`app.core.market` 的原因（那里顶层 `import pandas`）。
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

#: 市场时区的 IANA 名称。需要字符串形式的场合（Playwright 的 ``timezone_id``、
#: 日志与持久化字段）必须用它，避免另外写一份 ``"Asia/Shanghai"``。
SHANGHAI_TIMEZONE_NAME = "Asia/Shanghai"

#: 沪深 A 股使用的市场时区（港股的行情时间戳也按此时区解释）。
SHANGHAI_TIMEZONE = ZoneInfo(SHANGHAI_TIMEZONE_NAME)


def market_today() -> date:
    """返回市场时区（Asia/Shanghai）的当天日期。

    容器通常以 UTC 运行，而用户在浏览器里看到的是 Asia/Shanghai 日期。
    每天 00:00–08:00 CST 两者相差一天，若用 ``date.today()`` 校验「不能晚于今天」，
    用户提交的当日日期会被误判为未来日期而报错，因此业务日期一律走本函数。
    """
    return datetime.now(SHANGHAI_TIMEZONE).date()


__all__ = ["SHANGHAI_TIMEZONE", "SHANGHAI_TIMEZONE_NAME", "market_today"]
