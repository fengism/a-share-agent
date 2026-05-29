import logging
from datetime import datetime, timedelta

from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)



def _fallback_report_dates(report_date: str, days: int = 5) -> list[str]:
    base = datetime.strptime(report_date, "%Y-%m-%d")
    return [(base - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days)]


async def get_dragon_tiger_list(report_date: str | None = None) -> list[dict]:
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    cache_key = dated_cache_key("dragon_tiger", report_date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        for candidate_date in _fallback_report_dates(report_date):
            data = await call_blocking(_eastmoney_provider.fetch_dragon_tiger_daily_list, candidate_date)
            if data:
                result = data
                break
    except Exception as e:
        logger.warning(f"龙虎榜数据获取失败: {e}")

    cache.set(cache_key, result, ttl=600)
    return result


async def get_dragon_tiger_detail(code: str, report_date: str) -> list[dict]:
    cache_key = dated_cache_key("dragon_tiger_detail", code, report_date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        result = await call_blocking(_eastmoney_provider.fetch_dragon_tiger_stock_detail, code, report_date)
    except Exception as e:
        logger.warning(f"龙虎榜明细获取失败: {code}, {e}")

    cache.set(cache_key, result, ttl=600)
    return result
