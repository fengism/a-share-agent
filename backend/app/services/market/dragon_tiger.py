import logging
from datetime import datetime, timedelta

from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")



def _fallback_report_dates(report_date: str, days: int = 5) -> list[str]:
    """生成龙虎榜日期回退列表，从指定日期往前推 N 天。

    Param:
        report_date: 起始报告日期，格式 YYYY-MM-DD
        days: 回退天数
    Return:
        逆序日期字符串列表，最近的日期在前
    """
    base = datetime.strptime(report_date, "%Y-%m-%d")
    return [(base - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days)]


async def get_dragon_tiger_list(report_date: str | None = None) -> list[dict]:
    """获取指定日期的龙虎榜列表，带日期回退和缓存。

    Param:
        report_date: 报告日期，格式 YYYY-MM-DD，默认当天
    Return:
        龙虎榜条目字典列表，失败返回空列表
    """
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    cache_key = dated_cache_key("dragon_tiger", report_date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        for candidate_date in _fallback_report_dates(report_date):
            data = await call_blocking(_get_eastmoney_provider().fetch_dragon_tiger_daily_list, candidate_date)
            if data:
                result = data
                break
    except Exception as e:
        logger.warning(f"龙虎榜数据获取失败: {e}")

    cache.set(cache_key, result, ttl=600)
    return result


async def get_dragon_tiger_detail(code: str, report_date: str) -> list[dict]:
    """获取指定股票在指定日期的龙虎榜营业部明细。

    Param:
        code: 股票代码
        report_date: 报告日期，格式 YYYY-MM-DD
    Return:
        龙虎榜营业部明细字典列表，失败返回空列表
    """
    cache_key = dated_cache_key("dragon_tiger_detail", code, report_date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = []
    try:
        result = await call_blocking(_get_eastmoney_provider().fetch_dragon_tiger_stock_detail, code, report_date)
    except Exception as e:
        logger.warning(f"龙虎榜明细获取失败: {code}, {e}")

    cache.set(cache_key, result, ttl=600)
    return result
