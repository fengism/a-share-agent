from datetime import UTC, date, datetime

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, kaipanhong_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import MarketLimitUpLadderResponse
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE, resolve_market_data_cache_policy
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_limit_up_ladder_singleflight: AsyncSingleFlight[MarketLimitUpLadderResponse] = AsyncSingleFlight()


async def get_limit_up_ladder(requested_date: date | None = None) -> MarketLimitUpLadderResponse:
    """获取开盘红涨停天梯，复用日 K 交易时段缓存策略。"""
    target_date = requested_date or datetime.now(SHANGHAI_TIMEZONE).date()
    policy = await resolve_market_data_cache_policy("daily", target_date)
    date_text = target_date.isoformat()
    cache_key = dated_cache_key("market_limit_up_ladder", date_text)
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return MarketLimitUpLadderResponse.model_validate(cached)

    async def load_and_cache() -> MarketLimitUpLadderResponse:
        provider = get_provider("kaipanhong")
        try:
            data = await provider_gateway.call(
                "kaipanhong",
                "market_limit_up_ladder",
                lambda: call_blocking(
                    provider.fetch_limit_up_ladder,
                    date_text,
                    semaphore=kaipanhong_semaphore,
                ),
            )
            stocks = data.get("stocks") or []
            result = MarketLimitUpLadderResponse(
                date=data.get("date") or date_text,
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                total=len(stocks),
                stocks=stocks,
                sectors=data.get("sectors") or [],
            )
        except Exception as error:
            raise UpstreamUnavailableError("涨停天梯上游暂时不可用") from error
        if policy.write_cache and policy.ttl_seconds is not None:
            cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _limit_up_ladder_singleflight.do(cache_key, load_and_cache)
