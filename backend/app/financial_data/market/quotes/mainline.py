from datetime import UTC, datetime

from app.core.cache import dated_cache_key_no_day
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, cls_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import MarketMainlineResponse
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_MARKET_MAINLINE_CACHE_KEY = dated_cache_key_no_day("market_mainline", "v2")
_MARKET_MAINLINE_CACHE_TTL_SECONDS = 60
_market_mainline_singleflight: AsyncSingleFlight[MarketMainlineResponse] = AsyncSingleFlight()


async def get_market_mainline() -> MarketMainlineResponse:
    """获取财联社今日主线机会，使用独立短缓存保持内容及时更新。"""
    cached = cache.get(_MARKET_MAINLINE_CACHE_KEY)
    if cached is not None:
        return MarketMainlineResponse.model_validate(cached)

    async def load_and_cache() -> MarketMainlineResponse:
        cached_inside_flight = cache.get(_MARKET_MAINLINE_CACHE_KEY)
        if cached_inside_flight is not None:
            return MarketMainlineResponse.model_validate(cached_inside_flight)
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
        cache.set(
            _MARKET_MAINLINE_CACHE_KEY,
            result,
            ttl=_MARKET_MAINLINE_CACHE_TTL_SECONDS,
        )
        return result

    return await _market_mainline_singleflight.do(_MARKET_MAINLINE_CACHE_KEY, load_and_cache)
