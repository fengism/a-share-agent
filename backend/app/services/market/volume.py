import asyncio
import logging

from app.models.market import MarketVolume
from app.services.providers.akshare import akshare_provider as _akshare_provider
from app.services.providers.ths import ths_provider as _ths_provider
from app.utils.cache import cache, cache_date, dated_cache_key, one_year_ago_date
from app.utils.data_clean import safe_float
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)



async def get_market_volume(start_date: str = "", end_date: str = "") -> list[dict]:
    """获取上证指数成交量历史序列。

    Param:
        start_date: 起始日期，留空默认一年前
        end_date: 结束日期，留空默认当天
    Return:
        包含 date/volume/amount 字段的字典列表
    """
    if not end_date:
        end_date = cache_date()
    if not start_date:
        start_date = one_year_ago_date()

    cache_key = dated_cache_key("market_volume", start_date, end_date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        df = await call_blocking(
            _akshare_provider.fetch_index_kline,
            symbol="000001",
            period="daily",
            start_date=start_date,
            end_date=end_date,
        )
        for _, row in df.iterrows():
            result.append(
                {
                    "date": str(row.get("日期", "")),
                    "volume": safe_float(row.get("成交量")),
                    "amount": safe_float(row.get("成交额")),
                }
            )
    except Exception:
        logger.warning("大盘成交量数据获取失败")

    cache.set(cache_key, result, ttl=300)
    return result


async def get_market_volume_data() -> MarketVolume:
    """获取同花顺市场成交额实时数据。

    Param:
        无
    Return:
        MarketVolume 模型对象
    """
    return await call_blocking(_ths_provider.fetch_market_volume)


if __name__ == "__main__":
    result = asyncio.run(get_market_volume_data())
    print(result)
