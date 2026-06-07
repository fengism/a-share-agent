import asyncio
import logging

from app.models.market import MarketVolume
from app.services.market.index_kline import get_index_kline
from app.services.providers.ths import ths_provider as _ths_provider
from app.utils.cache import cache, cache_date, dated_cache_key, one_year_ago_date
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)

# 上证指数 + 深证成指
_INDEX_SYMBOLS = ("000001", "399001")


async def get_market_volume(start_date: str = "", end_date: str = "") -> list[dict]:
    """获取沪深两市（上证+深成）合计成交量/成交额历史序列。

    通过 get_index_kline 分别获取上证指数和深证成指的日K数据，
    按日期聚合两市的成交量和成交额总和。

    Param:
        start_date: 起始日期，留空默认一年前
        end_date: 结束日期，留空默认当天
    Return:
        包含 date/volume/amount 字段的字典列表，按日期升序排列
    """
    if not end_date:
        end_date = cache_date()
    if not start_date:
        start_date = one_year_ago_date()

    cache_key = dated_cache_key("market_volume", start_date, end_date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # 并发获取上证指数和深证成指的K线数据
    kline_results = await asyncio.gather(
        *[
            get_index_kline(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)
            for symbol in _INDEX_SYMBOLS
        ],
        return_exceptions=True,
    )

    # 按日期汇总成交量和成交额
    agg: dict[str, dict] = {}
    for result in kline_results:
        if isinstance(result, Exception):
            logger.warning("指数K线获取失败，跳过: %s", result)
            continue
        for item in result.items:
            # item.date 格式为 YYYYMMDD，转为 YYYY-MM-DD
            raw = item.date.replace("-", "")
            date_str = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 else raw
            if date_str not in agg:
                agg[date_str] = {"date": date_str, "volume": 0.0, "amount": 0.0}
            agg[date_str]["volume"] += item.volume or 0.0
            agg[date_str]["amount"] += item.amount or 0.0

    result = sorted(agg.values(), key=lambda x: x["date"])
    cache.set(cache_key, result, ttl=300)
    return result


async def get_realtime_market_volume() -> MarketVolume:
    """获取同花顺市场成交额实时数据。

    Param:
        无
    Return:
        MarketVolume 模型对象
    """
    return await call_blocking(_ths_provider.fetch_market_volume)


if __name__ == "__main__":
    result = asyncio.run(get_market_volume("20260501", "20260607"))
    print(result)
