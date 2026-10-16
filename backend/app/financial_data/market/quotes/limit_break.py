"""炸板股票池。

复盘需要「封板质量」这一维度：涨停家数只说明有多少股票封住，炸板家数才能
说明有多少股票盘中打开过涨停。上游只有 fuyao 提供按交易日的炸板池
（``/api/a-share/special-data/limit-break-pool``），因此本模块直接使用该数据源。

注意：该接口支持当日（收盘后），与开盘红的历史榜单（仅支持今天之前）不同，
所以复盘可以取用当天数据。
"""

from datetime import UTC, date, datetime
from typing import cast

from app.core.cache import dated_cache_key_no_day
from app.core.cache import market_cache as cache
from app.core.cache_policies import MARKET_LIMIT_BREAK_POOL
from app.core.concurrency.rate_limiter import call_blocking, fuyao_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import MarketLimitBreakPoolResponse
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_limit_break_singleflight: AsyncSingleFlight[MarketLimitBreakPoolResponse] = AsyncSingleFlight()


async def get_limit_break_pool(requested_date: date) -> MarketLimitBreakPoolResponse:
    """获取指定交易日的炸板股票池。"""
    date_text = requested_date.isoformat()
    cache_key = dated_cache_key_no_day("market_limit_break_pool", date_text)
    cached = cache.get(cache_key)
    if cached is not None:
        return cast(MarketLimitBreakPoolResponse, MarketLimitBreakPoolResponse.model_validate(cached))

    async def load_and_cache() -> MarketLimitBreakPoolResponse:
        provider = get_provider("fuyao")
        try:
            data = await provider_gateway.call(
                "fuyao",
                "limit_break_pool",
                lambda: call_blocking(
                    provider.fetch_limit_break_pool,
                    date_text,
                    semaphore=fuyao_semaphore,
                ),
            )
            items = data.get("items") or []
            result = MarketLimitBreakPoolResponse(
                date=data.get("date") or date_text,
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                total=len(items),
                items=items,
            )
        except Exception as error:
            raise UpstreamUnavailableError("炸板池上游暂时不可用") from error

        cache.set(cache_key, result, ttl=MARKET_LIMIT_BREAK_POOL.ttl_seconds)
        return result

    return cast(
        MarketLimitBreakPoolResponse,
        await _limit_break_singleflight.do(cache_key, load_and_cache),
    )
