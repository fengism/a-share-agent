from datetime import datetime

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.core.market import safe_float
from app.financial_data.stock.public import fetch_realtime_quote_set, get_stock_name_map
from app.infrastructure.persistence import watchlist as watchlist_store
from app.modules.watchlist.schemas import (
    WatchlistAlert,
    WatchlistAlertCreate,
    WatchlistItem,
    WatchlistItemCreate,
    WatchlistResponse,
)


class UnknownWatchlistStockError(ValueError):
    pass


class WatchlistItemNotFoundError(LookupError):
    pass


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


async def get_watchlist(user_id: int) -> WatchlistResponse:
    items = await call_blocking(watchlist_store.list_items, user_id, semaphore=database_semaphore)
    alerts = await call_blocking(watchlist_store.list_alerts, user_id, semaphore=database_semaphore)
    codes = [str(item["stock_code"]) for item in items]
    quote_set = await fetch_realtime_quote_set(codes) if codes else None
    quotes = quote_set.quotes if quote_set else {}
    quote_sources = quote_set.quote_sources if quote_set else {}
    alerts_by_code: dict[str, list[WatchlistAlert]] = {}
    for row in alerts:
        code = str(row["stock_code"])
        quote = quotes.get(code, {})
        condition = str(row["condition"])
        threshold = float(row["threshold"])
        alerts_by_code.setdefault(code, []).append(
            WatchlistAlert(
                id=int(row["id"]),
                stock_code=code,
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
        code = str(row["stock_code"])
        quote = quotes.get(code, {})
        response_items.append(
            WatchlistItem(
                id=int(row["id"]),
                stock_code=code,
                stock_name=str(quote.get("name") or row["stock_name"]),
                note=str(row["note"]),
                created_at=str(row["created_at"]),
                current_price=safe_float(quote.get("price")),
                change_pct=safe_float(quote.get("change_pct")),
                quote_source=quote_sources.get(code, ""),
                alerts=alerts_by_code.get(code, []),
            )
        )
    return WatchlistResponse(
        items=response_items,
        source=quote_set.source if quote_set else "",
        quoted_at=(quote_set.quoted_at if quote_set and quote_set.quoted_at else datetime.now().isoformat(timespec="seconds")),
    )


async def add_watchlist_item(request: WatchlistItemCreate, user_id: int) -> WatchlistItem:
    quote_set = await fetch_realtime_quote_set([request.stock_code])
    quote = quote_set.quotes.get(request.stock_code, {})
    stock_name = str(quote.get("name") or "").strip()
    if not stock_name:
        stock_name = (await get_stock_name_map()).get(request.stock_code, "")
    if not stock_name:
        raise UnknownWatchlistStockError(request.stock_code)
    row = await call_blocking(
        watchlist_store.add_item,
        user_id,
        request.stock_code,
        stock_name,
        request.note,
        semaphore=database_semaphore,
    )
    return WatchlistItem(
        **row,
        current_price=safe_float(quote.get("price")),
        change_pct=safe_float(quote.get("change_pct")),
        quote_source=quote_set.quote_sources.get(request.stock_code, ""),
    )


async def remove_watchlist_item(stock_code: str, user_id: int) -> bool:
    return await call_blocking(
        watchlist_store.delete_item,
        user_id,
        stock_code,
        semaphore=database_semaphore,
    )


async def add_watchlist_alert(stock_code: str, request: WatchlistAlertCreate, user_id: int) -> WatchlistAlert:
    item = await call_blocking(
        watchlist_store.get_item,
        user_id,
        stock_code,
        semaphore=database_semaphore,
    )
    if item is None:
        raise WatchlistItemNotFoundError(stock_code)
    row = await call_blocking(
        watchlist_store.add_alert,
        user_id,
        stock_code,
        request.condition,
        request.threshold,
        semaphore=database_semaphore,
    )
    return WatchlistAlert(
        id=int(row["id"]),
        stock_code=stock_code,
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
