from datetime import UTC, datetime

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, cls_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import MarketWindResponse, MarketWindStocksResponse
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE, resolve_market_data_cache_policy
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_market_wind_singleflight: AsyncSingleFlight[MarketWindResponse] = AsyncSingleFlight()
_market_wind_stocks_singleflight: AsyncSingleFlight[MarketWindStocksResponse] = AsyncSingleFlight()


async def get_market_wind() -> MarketWindResponse:
    """获取今日风口板块，复用日 K 交易时段缓存策略。"""
    policy = await resolve_market_data_cache_policy(
        "daily",
        datetime.now(SHANGHAI_TIMEZONE).date(),
    )
    cache_key = dated_cache_key("market_wind")
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return MarketWindResponse.model_validate(cached)

    async def load_and_cache() -> MarketWindResponse:
        provider = get_provider("cls")
        try:
            items = await provider_gateway.call(
                "cls",
                "market_wind",
                lambda: call_blocking(provider.fetch_market_wind, semaphore=cls_semaphore),
            )
            result = MarketWindResponse(
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                items=items,
            )
        except Exception as error:
            raise UpstreamUnavailableError("市场风口上游暂时不可用") from error
        if policy.write_cache and policy.ttl_seconds is not None:
            cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _market_wind_singleflight.do(cache_key, load_and_cache)


async def get_market_wind_stocks(plate_code: str) -> MarketWindStocksResponse:
    """获取风口板块龙头股，复用日 K 交易时段缓存策略。"""
    normalized_plate_code = plate_code.strip()
    if not normalized_plate_code:
        raise ValueError("plate_code 不能为空")
    policy = await resolve_market_data_cache_policy(
        "daily",
        datetime.now(SHANGHAI_TIMEZONE).date(),
    )
    cache_key = dated_cache_key("market_wind_stocks", normalized_plate_code)
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return MarketWindStocksResponse.model_validate(cached)

    async def load_and_cache() -> MarketWindStocksResponse:
        provider = get_provider("cls")
        try:
            items = await provider_gateway.call(
                "cls",
                "market_wind_stocks",
                lambda: call_blocking(
                    provider.fetch_market_wind_stocks,
                    normalized_plate_code,
                    semaphore=cls_semaphore,
                ),
            )
            result = MarketWindStocksResponse(
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                plate_code=normalized_plate_code,
                items=items,
            )
        except Exception as error:
            raise UpstreamUnavailableError("风口成分股上游暂时不可用") from error
        if policy.write_cache and policy.ttl_seconds is not None:
            cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _market_wind_stocks_singleflight.do(cache_key, load_and_cache)
