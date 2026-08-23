import logging
from datetime import UTC, datetime

from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import call_blocking, eastmoney_semaphore
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import MarketMarginItem, MarketMarginResponse
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_YI = 1e8


async def get_market_margin(days: int = 240) -> MarketMarginResponse:
    """获取沪深两市融资融券历史合计（日级，单位亿元），带当日缓存。"""
    days = max(30, min(days, 500))
    cache_key = dated_cache_key("market_margin")
    cached = cache.get(cache_key)
    if cached is not None:
        return MarketMarginResponse.model_validate(cached)

    provider = get_provider("eastmoney")
    try:
        rows = await provider_gateway.call(
            "eastmoney",
            "market_margin",
            lambda: call_blocking(provider.fetch_market_margin_summary, days, semaphore=eastmoney_semaphore),
        )
    except Exception as error:
        logger.warning("融资融券市场合计获取失败: %s", error)
        raise UpstreamUnavailableError("融资融券上游暂时不可用") from error

    result = MarketMarginResponse(
        items=[
            MarketMarginItem(
                date=row.get("date", ""),
                rzye=round(row["rzye"] / _YI, 2) if row.get("rzye") is not None else None,
                rqye=round(row["rqye"] / _YI, 2) if row.get("rqye") is not None else None,
                rzrqye=round(row["rzrqye"] / _YI, 2) if row.get("rzrqye") is not None else None,
                rzmre=round(row["rzmre"] / _YI, 2) if row.get("rzmre") is not None else None,
                rzche=round(row["rzche"] / _YI, 2) if row.get("rzche") is not None else None,
                rzjme=round(row["rzjme"] / _YI, 2) if row.get("rzjme") is not None else None,
            )
            for row in rows
        ],
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    cache.set(cache_key, result, ttl=600)
    return result
