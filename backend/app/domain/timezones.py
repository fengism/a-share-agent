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


def market_now() -> datetime:
    """返回市场时区的当前**墙上时间**（``tzinfo`` 已剥离，便于沿用既有字符串格式）。

    **为什么是 naive**：仓库里大量时间戳以 ``datetime.now().isoformat(timespec="seconds")``
    写入 SQLite 与用户存档（``quoted_at`` / ``saved_at`` / ``last_started_at`` …），
    并成对地以 ``datetime.fromisoformat`` 读回比较。改成带时区会改变已落库格式，
    需要数据迁移才能保持一致；这里只把**墙上时间**从"容器本地时区"钉到市场时区，
    格式与解析逻辑完全不变。

    需要的场景：容器默认是 UTC（``docker-compose`` 靠 ``TZ`` 环境变量纠正，
    裸机/k8s/dev/测试环境通常没有），此时 ``datetime.now()`` 会与用户在浏览器里看到的
    北京时间相差 8 小时——「行情时间」「生成时间」「今天」都会错。用本函数后结果与
    ``TZ`` 是否设置无关。

    新代码如果不受既有格式约束，应优先使用 ``datetime.now(SHANGHAI_TIMEZONE)``
    保留时区信息。

    **升级注意**：若某个部署此前在缺少 ``TZ=Asia/Shanghai`` 的环境里跑过（裸机/k8s），
    它已经落库的时间戳是 UTC 墙上时间，与现在写入的北京时间相差 8 小时。这类行只会
    影响"最近 N 小时"式的新鲜度判断，且集中在切换点附近，长期无副作用；如需彻底对齐，
    可按需修正那批历史行（没有通用脚本：每张表的时间语义不同）。
    """
    return datetime.now(SHANGHAI_TIMEZONE).replace(tzinfo=None)


def market_today() -> date:
    """返回市场时区（Asia/Shanghai）的当天日期。

    容器通常以 UTC 运行，而用户在浏览器里看到的是 Asia/Shanghai 日期。
    每天 00:00–08:00 CST 两者相差一天，若用 ``date.today()`` 校验「不能晚于今天」，
    用户提交的当日日期会被误判为未来日期而报错，因此业务日期一律走本函数。
    """
    return datetime.now(SHANGHAI_TIMEZONE).date()


__all__ = ["SHANGHAI_TIMEZONE", "SHANGHAI_TIMEZONE_NAME", "market_now", "market_today"]
