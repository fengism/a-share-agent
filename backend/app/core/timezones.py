"""市场时间基准。

沪深 A 股行情、交易日历、复盘日期与港股行情对齐都统一使用 ``Asia/Shanghai``。
此前该常量在 26 处各写一份（12 个模块级私有别名 + 14 处内联 ``ZoneInfo(...)``），
一旦有人改错其中一个就会导致跨模块的日期口径不一致（而且很难排查）。

本模块刻意**不依赖 pandas 等重型依赖**，因此任何层次都可以安全导入——这也是它没有
放在 :mod:`app.core.market` 的原因（那里顶层 `import pandas`）。
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

#: 市场时区的 IANA 名称。需要字符串形式的场合（Playwright 的 ``timezone_id``、
#: 日志与持久化字段）必须用它，避免另外写一份 ``"Asia/Shanghai"``。
SHANGHAI_TIMEZONE_NAME = "Asia/Shanghai"

#: 沪深 A 股使用的市场时区（港股的行情时间戳也按此时区解释）。
SHANGHAI_TIMEZONE = ZoneInfo(SHANGHAI_TIMEZONE_NAME)

__all__ = ["SHANGHAI_TIMEZONE", "SHANGHAI_TIMEZONE_NAME"]
