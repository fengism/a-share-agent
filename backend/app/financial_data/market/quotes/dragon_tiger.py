import logging
from datetime import date, datetime

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, eastmoney_semaphore
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE, get_market_date_on_or_before
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


async def get_dragon_tiger_list(report_date: str | None = None) -> list[dict]:
    """获取指定日期的龙虎榜列表，带日期回退和缓存。

    Param:
        report_date: 报告日期，格式 YYYY-MM-DD，默认当天
    Return:
        龙虎榜条目字典列表，失败返回空列表
    """
    requested_date = (
        date.fromisoformat(report_date) if report_date is not None else datetime.now(SHANGHAI_TIMEZONE).date()
    )
    target_date = await get_market_date_on_or_before(requested_date)
    target_date_text = target_date.isoformat()

    cache_key = dated_cache_key("dragon_tiger", target_date_text)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        result = await provider_gateway.call(
            "eastmoney",
            "dragon_tiger_list",
            lambda: call_blocking(
                _get_eastmoney_provider().fetch_dragon_tiger_daily_list,
                target_date_text,
                semaphore=eastmoney_semaphore,
            ),
        )
    except Exception as error:
        logger.warning("龙虎榜数据获取失败: %s", error)
        raise UpstreamUnavailableError("龙虎榜上游暂时不可用") from error

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

    try:
        result = await provider_gateway.call(
            "eastmoney",
            "dragon_tiger_detail",
            lambda: call_blocking(
                _get_eastmoney_provider().fetch_dragon_tiger_stock_detail,
                code,
                report_date,
                semaphore=eastmoney_semaphore,
            ),
        )
    except Exception as error:
        logger.warning("龙虎榜明细获取失败: code=%s error=%s", code, error)
        raise UpstreamUnavailableError("龙虎榜明细上游暂时不可用") from error

    cache.set(cache_key, result, ttl=600)
    return result
