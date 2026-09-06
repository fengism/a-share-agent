from datetime import UTC, datetime

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, cls_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import MarketEmotion
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE, resolve_market_data_cache_policy
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_market_emotion_singleflight: AsyncSingleFlight[MarketEmotion] = AsyncSingleFlight()


async def get_market_emotion() -> MarketEmotion:
    """获取财联社市场情绪数据，复用日 K 交易时段缓存策略。"""
    policy = await resolve_market_data_cache_policy(
        "daily",
        datetime.now(SHANGHAI_TIMEZONE).date(),
    )
    cache_key = dated_cache_key("market_emotion")
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return MarketEmotion.model_validate(cached)

    async def _load() -> MarketEmotion:
        provider = get_provider("cls")
        try:
            data = await provider_gateway.call(
                "cls",
                "market_emotion",
                lambda: call_blocking(provider.fetch_market_emotion, semaphore=cls_semaphore),
            )
            result = MarketEmotion(
                **data,
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        except Exception as error:
            raise UpstreamUnavailableError("市场情绪上游暂时不可用") from error
        if policy.write_cache and policy.ttl_seconds is not None:
            cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _market_emotion_singleflight.do(cache_key, _load)
