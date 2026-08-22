from datetime import UTC, datetime

from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import call_blocking, cls_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import MarketMainlineResponse
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE, resolve_market_data_cache_policy
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_market_mainline_singleflight: AsyncSingleFlight[MarketMainlineResponse] = AsyncSingleFlight()


async def get_market_mainline() -> MarketMainlineResponse:
    """获取财联社今日主线机会，复用日 K 交易时段缓存策略。"""
    policy = await resolve_market_data_cache_policy(
        "daily",
        datetime.now(SHANGHAI_TIMEZONE).date(),
    )
    cache_key = dated_cache_key("market_mainline")
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return MarketMainlineResponse.model_validate(cached)

    async def load_and_cache() -> MarketMainlineResponse:
        provider = get_provider("cls")
        try:
            data = await provider_gateway.call(
                "cls",
                "market_mainline",
                lambda: call_blocking(provider.fetch_market_mainline, semaphore=cls_semaphore),
            )
            result = MarketMainlineResponse(
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                style=data.get("style"),
                items=data.get("chances") or [],
            )
        except Exception as error:
            raise UpstreamUnavailableError("市场主线上游暂时不可用") from error
        if policy.write_cache and policy.ttl_seconds is not None:
            cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _market_mainline_singleflight.do(cache_key, load_and_cache)
