from datetime import UTC, date, datetime
from typing import cast

from app.core.cache import dated_cache_key_no_day
from app.core.cache import market_cache as cache
from app.core.cache_policies import MARKET_SECTOR_STOCKS_HISTORY
from app.core.concurrency.rate_limiter import call_blocking, kaipanhong_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import InvalidRequestError, UpstreamUnavailableError
from app.financial_data.market.quotes.schemas import (
    MarketSectorStocksHistoryResponse,
)
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

_sector_stocks_singleflight: AsyncSingleFlight[MarketSectorStocksHistoryResponse] = (
    AsyncSingleFlight()
)


def _shanghai_today() -> date:
    return datetime.now(SHANGHAI_TIMEZONE).date()


async def get_sector_stocks_history(
    requested_date: date,
    plate_id: str,
) -> MarketSectorStocksHistoryResponse:
    """获取开盘红板块在指定历史日期的成分股列表。"""
    normalized_plate_id = plate_id.strip()
    if not normalized_plate_id:
        raise InvalidRequestError("plate_id 不能为空")
    if requested_date >= _shanghai_today():
        raise InvalidRequestError("板块历史成分股仅支持今天之前的日期")

    date_text = requested_date.isoformat()
    cache_key = dated_cache_key_no_day(
        "market_sector_stocks_history",
        date_text,
        normalized_plate_id,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cast(
            MarketSectorStocksHistoryResponse,
            MarketSectorStocksHistoryResponse.model_validate(cached),
        )

    async def load_and_cache() -> MarketSectorStocksHistoryResponse:
        provider = get_provider("kaipanhong")
        try:
            data = await provider_gateway.call(
                "kaipanhong",
                "sector_stocks_history",
                lambda: call_blocking(
                    provider.fetch_sector_stocks_history,
                    date_text,
                    normalized_plate_id,
                    semaphore=kaipanhong_semaphore,
                ),
            )
            stocks = data.get("stocks") or []
            result = MarketSectorStocksHistoryResponse(
                date=data.get("date") or date_text,
                plate_id=data.get("plate_id") or normalized_plate_id,
                fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
                total=len(stocks),
                items=stocks,
            )
        except InvalidRequestError:
            raise
        except Exception as error:
            raise UpstreamUnavailableError("板块成分股上游暂时不可用") from error

        cache.set(cache_key, result, ttl=MARKET_SECTOR_STOCKS_HISTORY.ttl_seconds)
        return result

    return cast(
        MarketSectorStocksHistoryResponse,
        await _sector_stocks_singleflight.do(cache_key, load_and_cache),
    )
