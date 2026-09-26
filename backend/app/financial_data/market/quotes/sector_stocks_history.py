import logging
from datetime import UTC, date, datetime, timedelta
from typing import cast

from app.core.cache import dated_cache_key_no_day
from app.core.cache import market_cache as cache
from app.core.cache_policies import MARKET_SECTOR_STOCKS_HISTORY
from app.core.concurrency.rate_limiter import call_blocking, kaipanhong_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import InvalidRequestError, UpstreamUnavailableError
from app.core.market import market_today, normalize_code, safe_float
from app.financial_data.market.quotes.schemas import (
    MarketSectorStocksHistoryResponse,
)
from app.financial_data.market.trading_session import (
    SHANGHAI_TIMEZONE,
    get_market_date_on_or_before,
)
from app.financial_data.stock.quotes.realtime import fetch_realtime_quote_set
from app.infrastructure.persistence.sector_constituent_store import (
    load_snapshot as load_sector_snapshot,
)
from app.infrastructure.persistence.sector_constituent_store import (
    replace_snapshot as save_sector_snapshot,
)
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_sector_stocks_singleflight: AsyncSingleFlight[MarketSectorStocksHistoryResponse] = (
    AsyncSingleFlight()
)



def _response_from_snapshot(
    data: dict,
    *,
    requested_date: date,
    plate_id: str,
) -> MarketSectorStocksHistoryResponse:
    stocks = data.get("stocks")
    if stocks is None:
        stocks = data.get("items") or []
    constituent_date = str(
        data.get("constituent_date") or data.get("date") or requested_date.isoformat()
    )
    return MarketSectorStocksHistoryResponse(
        date=str(data.get("date") or constituent_date),
        constituent_date=constituent_date,
        plate_id=str(data.get("plate_id") or plate_id),
        fetched_at=str(data.get("fetched_at") or datetime.now(UTC).isoformat(timespec="seconds")),
        history_details_available=True,
        total=len(stocks),
        items=stocks,
    )


def _normalize_history_stocks(stocks: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()
    for stock in stocks:
        try:
            code = normalize_code(str(stock.get("code") or "")).raw
        except ValueError:
            logger.warning("跳过无效板块成分股代码: %s", stock.get("code"))
            continue
        if code in seen:
            continue
        seen.add(code)
        normalized.append({**stock, "code": code})
    return normalized


def _quote_date(quoted_at: object) -> date | None:
    text = str(quoted_at or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(SHANGHAI_TIMEZONE)
    return parsed.date()


def _quote_is_current(
    quote: dict,
    *,
    requested_date: date,
    fallback_quoted_at: str | None,
) -> bool:
    quoted_at = quote.get("quoted_at") or fallback_quoted_at
    quote_day = _quote_date(quoted_at)
    return quote_day is None or quote_day == requested_date


def _build_latest_item(
    stock: dict,
    quote: dict | None,
    *,
    quote_source: str | None,
    fallback_quoted_at: str | None,
) -> dict:
    """当天只暴露身份信息及现价、涨跌幅、成交额，不混入历史交易指标。"""
    name = str(stock.get("name") or "").strip()
    if quote is not None:
        name = str(quote.get("name") or "").strip() or name

    item = {
        "code": stock["code"],
        "name": name,
        "tags": str(stock.get("tags") or ""),
        "price": None,
        "change_pct": None,
        "amount": None,
        "quote_source": None,
        "quoted_at": None,
    }
    if quote is None:
        return item

    item["price"] = safe_float(quote.get("price"))
    item["change_pct"] = safe_float(quote.get("change_pct"))
    amount = safe_float(quote.get("amount"))
    item["amount"] = int(amount) if amount is not None else None
    item["quote_source"] = quote_source
    item["quoted_at"] = str(quote.get("quoted_at") or fallback_quoted_at or "") or None
    return item


async def _get_historical_snapshot(
    requested_date: date,
    plate_id: str,
) -> MarketSectorStocksHistoryResponse:
    date_text = requested_date.isoformat()
    cache_key = dated_cache_key_no_day(
        "market_sector_stocks_history",
        date_text,
        plate_id,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cast(
            MarketSectorStocksHistoryResponse,
            MarketSectorStocksHistoryResponse.model_validate(cached),
        )

    async def load_and_cache() -> MarketSectorStocksHistoryResponse:
        try:
            stored = load_sector_snapshot("kaipanhong", plate_id, date_text)
        except Exception as error:
            logger.warning(
                "板块成分股数据库读取失败，改查开盘红 API: plate_id=%s, date=%s, error=%s",
                plate_id,
                date_text,
                error,
            )
            stored = None
        if stored is not None:
            result = _response_from_snapshot(
                stored,
                requested_date=requested_date,
                plate_id=plate_id,
            )
            cache.set(cache_key, result, ttl=MARKET_SECTOR_STOCKS_HISTORY.ttl_seconds)
            return result

        provider = get_provider("kaipanhong")
        try:
            data = await provider_gateway.call(
                "kaipanhong",
                "sector_stocks_history",
                lambda: call_blocking(
                    provider.fetch_sector_stocks_history,
                    date_text,
                    plate_id,
                    semaphore=kaipanhong_semaphore,
                ),
            )
            stocks = _normalize_history_stocks(data.get("stocks") or [])
            actual_date = str(data.get("date") or date_text)
            fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
            result = MarketSectorStocksHistoryResponse(
                date=actual_date,
                constituent_date=actual_date,
                plate_id=data.get("plate_id") or plate_id,
                fetched_at=fetched_at,
                history_details_available=True,
                total=len(stocks),
                items=stocks,
            )
            try:
                save_sector_snapshot(
                    source="kaipanhong",
                    plate_id=result.plate_id,
                    constituent_date=result.constituent_date,
                    fetched_at=fetched_at,
                    stocks=stocks,
                )
            except Exception as error:
                logger.warning(
                    "板块成分股数据库写入失败: plate_id=%s, date=%s, error=%s",
                    result.plate_id,
                    result.constituent_date,
                    error,
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


async def _get_latest_snapshot(
    requested_date: date,
    plate_id: str,
) -> MarketSectorStocksHistoryResponse:
    constituent_date = await get_market_date_on_or_before(requested_date - timedelta(days=1))
    history = await _get_historical_snapshot(constituent_date, plate_id)
    stock_rows = _normalize_history_stocks(
        [item.model_dump(mode="python") for item in history.items]
    )
    codes = [item["code"] for item in stock_rows]

    quote_set = None
    if codes:
        try:
            quote_set = await fetch_realtime_quote_set(codes)
            if quote_set.stale:
                quote_set = None
        except Exception as error:
            logger.warning(
                "板块成分股当天行情不可用，不回退历史交易数据: plate_id=%s, constituent_date=%s, error=%s",
                plate_id,
                history.constituent_date,
                error,
            )

    quotes: dict[str, dict] = {}
    quote_sources: dict[str, str] = {}
    if quote_set is not None:
        for raw_code, quote in quote_set.quotes.items():
            if not isinstance(quote, dict):
                continue
            try:
                code = normalize_code(str(raw_code)).raw
            except ValueError:
                continue
            if _quote_is_current(
                quote,
                requested_date=requested_date,
                fallback_quoted_at=quote_set.quoted_at,
            ):
                quotes[code] = quote
                source = quote_set.quote_sources.get(raw_code)
                if source:
                    quote_sources[code] = source

    items = [
        _build_latest_item(
            stock,
            quotes.get(stock["code"]),
            quote_source=quote_sources.get(stock["code"]),
            fallback_quoted_at=quote_set.quoted_at if quote_set is not None else None,
        )
        for stock in stock_rows
    ]
    quoted_count = sum(stock["code"] in quotes for stock in stock_rows)
    has_realtime = quoted_count > 0
    return MarketSectorStocksHistoryResponse(
        date=requested_date.isoformat(),
        constituent_date=history.constituent_date,
        plate_id=history.plate_id,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        quoted_at=(quote_set.quoted_at or None) if has_realtime and quote_set is not None else None,
        quote_source=quote_set.source if has_realtime and quote_set is not None else None,
        is_realtime=has_realtime,
        realtime_partial=bool(items) and quoted_count < len(items),
        history_details_available=False,
        total=len(items),
        items=items,
    )


async def get_sector_stocks_history(
    requested_date: date,
    plate_id: str,
) -> MarketSectorStocksHistoryResponse:
    """获取板块成分股；交易日当天仅补充三项实时行情，非交易日返回历史快照。"""
    normalized_plate_id = plate_id.strip()
    if not normalized_plate_id:
        raise InvalidRequestError("plate_id 不能为空")

    today = market_today()
    if requested_date > today:
        raise InvalidRequestError("板块成分股日期不能晚于今天")
    if requested_date < today:
        return await _get_historical_snapshot(requested_date, normalized_plate_id)

    market_date = await get_market_date_on_or_before(requested_date)
    if market_date < requested_date:
        history = await _get_historical_snapshot(market_date, normalized_plate_id)
        return history.model_copy(
            update={
                "date": requested_date.isoformat(),
                "history_details_available": True,
                "is_realtime": False,
                "realtime_partial": False,
            }
        )

    live_key = dated_cache_key_no_day(
        "market_sector_stocks_latest",
        requested_date.isoformat(),
        normalized_plate_id,
    )
    return cast(
        MarketSectorStocksHistoryResponse,
        await _sector_stocks_singleflight.do(
            live_key,
            lambda: _get_latest_snapshot(requested_date, normalized_plate_id),
        ),
    )
