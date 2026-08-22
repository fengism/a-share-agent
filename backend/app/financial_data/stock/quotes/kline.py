"""个股 K 线服务。"""

from datetime import date

from app.core.cache import cache, cache_date, dated_cache_key_no_day, one_year_ago_date
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import SymbolFormats, normalize_code
from app.domain.market import KlineData
from app.financial_data.dates import parse_market_date
from app.financial_data.market.trading_session import resolve_market_data_cache_policy
from app.financial_data.stock.quotes.historical import get_historical_bars

_kline_singleflight = AsyncSingleFlight[KlineData]()


async def _load_kline(
    sym: SymbolFormats,
    period: str,
    start_date: date,
    end_date: date,
    adjust: str,
) -> KlineData:
    """通过严格历史行情链加载 K 线并保留数据来源信息。

    Param:
        sym: 归一化后的代码对象
        period: K 线周期
        start_date: 起始日期
        end_date: 结束日期
        adjust: 复权类型
    Return:
        KlineData 模型对象
    """
    bars = await get_historical_bars(
        sym.raw,
        start_date,
        end_date,
        period=period,
        adjust=adjust,
    )
    return KlineData(
        code=bars.code,
        period=bars.period,
        adjust=bars.adjust,
        source=bars.source,
        adjustment_verified=bars.adjustment_verified,
        items=bars.items,
    )


async def get_kline(
    code: str, period: str = "daily", start_date: str = "", end_date: str = "", adjust: str = "qfq"
) -> KlineData:
    """获取股票 K 线数据，带 single-flight 与交易时段感知缓存。

    Param:
        code: 股票代码
        period: K 线周期，默认 daily
        start_date: 起始日期，留空默认一年前
        end_date: 结束日期，留空默认当天
        adjust: 复权类型，默认 qfq
    Return:
        KlineData 模型对象
    """
    sym = normalize_code(code)
    today = cache_date()
    if not end_date:
        end_date = today
    if not start_date:
        start_date = one_year_ago_date()

    parsed_start_date = parse_market_date(start_date, "start_date")
    parsed_end_date = parse_market_date(end_date, "end_date")
    if parsed_start_date > parsed_end_date:
        raise ValueError("start_date 不能晚于 end_date")

    policy = await resolve_market_data_cache_policy(period, parsed_end_date)
    cache_key = dated_cache_key_no_day(
        "kline",
        sym.raw,
        period,
        parsed_start_date.isoformat(),
        parsed_end_date.isoformat(),
        adjust,
    )
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    async def load_and_cache() -> KlineData:
        """加载 K 线数据并写入缓存。

        Param:
            无
        Return:
            KlineData 模型对象
        """
        result = await _load_kline(sym, period, parsed_start_date, parsed_end_date, adjust)
        if policy.write_cache and policy.ttl_seconds is not None:
            cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _kline_singleflight.do(cache_key, load_and_cache)
