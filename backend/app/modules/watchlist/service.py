import asyncio
from datetime import datetime

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.market import normalize_code, safe_float
from app.financial_data.hk.service import hk_market_service, normalize_hk_code
from app.financial_data.stock.public import fetch_realtime_quote_set, get_stock_concept_map, get_stock_name_map
from app.infrastructure.persistence import watchlist as watchlist_store
from app.modules.watchlist.schemas import (
    WatchlistAlert,
    WatchlistAlertCreate,
    WatchlistItem,
    WatchlistItemCreate,
    WatchlistMarket,
    WatchlistResponse,
)

_HK_STORAGE_PREFIX = "HK:"


class UnknownWatchlistStockError(ValueError):
    pass


class WatchlistItemNotFoundError(LookupError):
    pass


def storage_stock_code(market: WatchlistMarket, stock_code: str) -> str:
    return f"{_HK_STORAGE_PREFIX}{stock_code}" if market == "hk" else stock_code


def public_stock_identity(storage_code: str) -> tuple[WatchlistMarket, str]:
    if storage_code.startswith(_HK_STORAGE_PREFIX):
        return "hk", storage_code[len(_HK_STORAGE_PREFIX):]
    return "cn", storage_code


def normalize_watchlist_code(stock_code: str, market: WatchlistMarket) -> str:
    return normalize_hk_code(stock_code) if market == "hk" else normalize_code(stock_code).raw


def alert_current_value(condition: str, quote: dict) -> float | None:
    field = "change_pct" if condition.startswith("change_pct_") else "price"
    return safe_float(quote.get(field))


def is_alert_triggered(condition: str, threshold: float, quote: dict) -> bool:
    current_value = alert_current_value(condition, quote)
    if current_value is None:
        return False
    if condition.endswith("_above"):
        return current_value >= threshold
    return current_value <= threshold


def _previous_close(quote: dict) -> float | None:
    value = quote.get("last_close")
    return safe_float(value if value is not None else quote.get("pre_close"))


def _watchlist_item_from_quote(
    row: dict,
    *,
    market: WatchlistMarket,
    public_code: str,
    quote: dict,
    quote_source: str,
    concepts: list,
    alerts: list[WatchlistAlert] | None = None,
) -> WatchlistItem:
    return WatchlistItem(
        id=int(row["id"]),
        stock_code=public_code,
        market=market,
        stock_name=str(quote.get("name") or row["stock_name"]),
        note=str(row["note"]),
        created_at=str(row["created_at"]),
        current_price=safe_float(quote.get("price")),
        change_pct=safe_float(quote.get("change_pct")),
        open_price=safe_float(quote.get("open")),
        high_price=safe_float(quote.get("high")),
        low_price=safe_float(quote.get("low")),
        previous_close=_previous_close(quote),
        volume=safe_float(quote.get("volume")),
        amount=safe_float(quote.get("amount")),
        turnover_pct=safe_float(quote.get("turnover_pct")),
        pe_ttm=safe_float(quote.get("pe_ttm")),
        market_cap=safe_float(quote.get("mcap")),
        quote_source=quote_source,
        concepts=concepts,
        alerts=alerts or [],
    )


async def get_watchlist(user_id: int) -> WatchlistResponse:
    items = await call_blocking(watchlist_store.list_items, user_id, semaphore=database_semaphore)
    alerts = await call_blocking(watchlist_store.list_alerts, user_id, semaphore=database_semaphore)
    identities = [public_stock_identity(str(item["stock_code"])) for item in items]
    cn_codes = [code for market, code in identities if market == "cn"]
    hk_codes = [code for market, code in identities if market == "hk"]

    cn_quote_future = (
        asyncio.gather(fetch_realtime_quote_set(cn_codes), get_stock_concept_map(cn_codes))
        if cn_codes
        else None
    )
    hk_quote_future = (
        asyncio.create_task(
            hk_market_service.get_stock_quotes(
                codes=hk_codes,
                page=1,
                page_size=max(len(hk_codes), 1),
            )
        )
        if hk_codes
        else None
    )

    if cn_quote_future is not None:
        quote_set, concept_map = await cn_quote_future
    else:
        quote_set = None
        concept_map = {}
    hk_quote_page = await hk_quote_future if hk_quote_future is not None else None

    quotes: dict[str, dict] = {}
    quote_sources: dict[str, str] = {}
    if quote_set is not None:
        quotes.update(quote_set.quotes)
        quote_sources.update(quote_set.quote_sources)
    if hk_quote_page is not None:
        for quote in hk_quote_page.items:
            storage_code = storage_stock_code("hk", quote.code)
            quotes[storage_code] = quote.model_dump()
            quote_sources[storage_code] = hk_quote_page.source

    alerts_by_code: dict[str, list[WatchlistAlert]] = {}
    for row in alerts:
        storage_code = str(row["stock_code"])
        market, public_code = public_stock_identity(storage_code)
        quote = quotes.get(storage_code, {})
        condition = str(row["condition"])
        threshold = float(row["threshold"])
        alerts_by_code.setdefault(storage_code, []).append(
            WatchlistAlert(
                id=int(row["id"]),
                stock_code=public_code,
                market=market,
                condition=condition,
                threshold=threshold,
                enabled=bool(row["enabled"]),
                triggered=bool(row["enabled"]) and is_alert_triggered(condition, threshold, quote),
                current_value=alert_current_value(condition, quote),
                created_at=str(row["created_at"]),
            )
        )

    response_items = []
    for row in items:
        storage_code = str(row["stock_code"])
        market, public_code = public_stock_identity(storage_code)
        response_items.append(
            _watchlist_item_from_quote(
                row,
                market=market,
                public_code=public_code,
                quote=quotes.get(storage_code, {}),
                quote_source=quote_sources.get(storage_code, ""),
                concepts=concept_map.get(public_code, []) if market == "cn" else [],
                alerts=alerts_by_code.get(storage_code, []),
            )
        )

    if cn_codes and hk_codes:
        source = "mixed"
        quoted_at = datetime.now().isoformat(timespec="seconds")
    elif quote_set is not None:
        source = quote_set.source
        quoted_at = quote_set.quoted_at or datetime.now().isoformat(timespec="seconds")
    elif hk_quote_page is not None:
        source = hk_quote_page.source
        quoted_at = hk_quote_page.updated_at or datetime.now().isoformat(timespec="seconds")
    else:
        source = ""
        quoted_at = datetime.now().isoformat(timespec="seconds")
    return WatchlistResponse(items=response_items, source=source, quoted_at=quoted_at)


async def add_watchlist_item(request: WatchlistItemCreate, user_id: int) -> WatchlistItem:
    if request.market == "hk":
        quote_page = await hk_market_service.get_stock_quotes(
            codes=[request.stock_code],
            page=1,
            page_size=1,
        )
        stock_quote = next((item for item in quote_page.items if item.code == request.stock_code), None)
        quote = stock_quote.model_dump() if stock_quote is not None else {}
        stock_name = str(quote.get("name") or "").strip()
        quote_source = quote_page.source
        concepts = []
    else:
        quote_set, concept_map = await asyncio.gather(
            fetch_realtime_quote_set([request.stock_code]),
            get_stock_concept_map([request.stock_code]),
        )
        quote = quote_set.quotes.get(request.stock_code, {})
        stock_name = str(quote.get("name") or "").strip()
        if not stock_name:
            stock_name = (await get_stock_name_map()).get(request.stock_code, "")
        quote_source = quote_set.quote_sources.get(request.stock_code, "")
        concepts = concept_map.get(request.stock_code, [])

    if not stock_name:
        raise UnknownWatchlistStockError(request.stock_code)
    storage_code = storage_stock_code(request.market, request.stock_code)
    row = await call_blocking(
        watchlist_store.add_item,
        user_id,
        storage_code,
        stock_name,
        request.note,
        semaphore=database_semaphore,
    )
    return _watchlist_item_from_quote(
        row,
        market=request.market,
        public_code=request.stock_code,
        quote=quote,
        quote_source=quote_source,
        concepts=concepts,
    )


async def remove_watchlist_item(
    stock_code: str,
    user_id: int,
    market: WatchlistMarket = "cn",
) -> bool:
    public_code = normalize_watchlist_code(stock_code, market)
    return await call_blocking(
        watchlist_store.delete_item,
        user_id,
        storage_stock_code(market, public_code),
        semaphore=database_semaphore,
    )


async def add_watchlist_alert(stock_code: str, request: WatchlistAlertCreate, user_id: int) -> WatchlistAlert:
    public_code = normalize_watchlist_code(stock_code, request.market)
    storage_code = storage_stock_code(request.market, public_code)
    item = await call_blocking(
        watchlist_store.get_item,
        user_id,
        storage_code,
        semaphore=database_semaphore,
    )
    if item is None:
        raise WatchlistItemNotFoundError(public_code)
    row = await call_blocking(
        watchlist_store.add_alert,
        user_id,
        storage_code,
        request.condition,
        request.threshold,
        semaphore=database_semaphore,
    )
    return WatchlistAlert(
        id=int(row["id"]),
        stock_code=public_code,
        market=request.market,
        condition=row["condition"],
        threshold=float(row["threshold"]),
        enabled=bool(row["enabled"]),
        created_at=str(row["created_at"]),
    )


async def remove_watchlist_alert(alert_id: int, user_id: int) -> bool:
    return await call_blocking(
        watchlist_store.delete_alert,
        user_id,
        alert_id,
        semaphore=database_semaphore,
    )
