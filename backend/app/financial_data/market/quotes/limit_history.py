from datetime import UTC, date, datetime
from typing import cast

from app.core.cache import dated_cache_key_no_day
from app.core.cache import market_cache as cache
from app.core.cache_policies import MARKET_LIMIT_HISTORY
from app.core.concurrency.rate_limiter import call_blocking, kaipanhong_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import InvalidRequestError, UpstreamUnavailableError
from app.core.market import market_today
from app.financial_data.market.quotes.schemas import (
    MarketLimitHistoryCategory,
    MarketLimitHistoryResponse,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_limit_history_singleflight: AsyncSingleFlight[MarketLimitHistoryResponse] = AsyncSingleFlight()



async def get_limit_history(
    requested_date: date,
    category: MarketLimitHistoryCategory,
) -> MarketLimitHistoryResponse:
    """获取开盘红历史涨停、跌停或风向标列表。"""
    if requested_date >= market_today():
        raise InvalidRequestError("开盘红历史榜单仅支持今天之前的日期")

    date_text = requested_date.isoformat()
    cache_key = dated_cache_key_no_day("market_limit_history", date_text, category)
    cached = cache.get(cache_key)
    if cached is not None:
        return cast(MarketLimitHistoryResponse, MarketLimitHistoryResponse.model_validate(cached))

    async def load_and_cache() -> MarketLimitHistoryResponse:
        provider = get_provider("kaipanhong")
        try:
            data = await provider_gateway.call(
                "kaipanhong",
                "market_limit_history",
                lambda: call_blocking(
                    provider.fetch_limit_history,
                    date_text,
                    category,
                    semaphore=kaipanhong_semaphore,
                ),
            )
            items = data.get("items") or []
            result = MarketLimitHistoryResponse(
                date=data.get("date") or date_text,
                category=category,
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                total=len(items),
                items=items,
            )
        except InvalidRequestError:
            raise
        except Exception as error:
            raise UpstreamUnavailableError("历史涨跌停上游暂时不可用") from error

        cache.set(cache_key, result, ttl=MARKET_LIMIT_HISTORY.ttl_seconds)
        return result

    return cast(
        MarketLimitHistoryResponse,
        await _limit_history_singleflight.do(cache_key, load_and_cache),
    )
