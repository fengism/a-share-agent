import app.modules.portfolio.accounting as portfolio_accounting
import app.modules.portfolio.builder as portfolio_builder
from app.core.concurrency.rate_limiter import (
    call_blocking,
    database_semaphore,
)
from app.financial_data.stock.public import get_stock_name_map
from app.infrastructure.persistence import portfolio as portfolio_store
from app.modules.portfolio.accounting import (
    InsufficientSharesError,
    LedgerReplay,
    replay_transactions,
)
from app.modules.portfolio.quotes import fetch_quotes
from app.modules.portfolio.schemas import (
    PortfolioTransaction,
    PortfolioTransactionCreate,
    PortfolioTransactionPreview,
)


class PortfolioTransactionNotFoundError(LookupError):
    pass


class UnknownPortfolioStockError(ValueError):
    pass


async def _resolve_stock(request: PortfolioTransactionCreate, user_id: int) -> tuple[str, dict] | None:
    existing_name = await call_blocking(
        portfolio_store.get_latest_stock_name,
        user_id,
        request.stock_code,
        semaphore=database_semaphore,
    )
    if request.side == "sell" and existing_name:
        return existing_name, {}
    quotes = await fetch_quotes([request.stock_code])
    quote = quotes.get(request.stock_code, {})
    stock_name = str(quote.get("name") or existing_name).strip()
    if not stock_name:
        stock_name = (await get_stock_name_map()).get(request.stock_code, "")
    if not stock_name:
        return None
    return stock_name, quote


def _persist_transaction(
    request: PortfolioTransactionCreate,
    user_id: int,
    stock_name: str,
) -> tuple[dict, LedgerReplay]:
    validated_replay: LedgerReplay | None = None

    def validate(rows: list[dict]) -> LedgerReplay:
        nonlocal validated_replay
        validated_replay = replay_transactions(rows)
        return validated_replay

    row = portfolio_store.create_transaction(
        user_id,
        request.stock_code,
        stock_name,
        request.side,
        request.trade_price,
        request.trade_time.isoformat(timespec="seconds"),
        request.shares,
        request.fee,
        request.note,
        validator=validate,
    )
    if validated_replay is None:
        raise RuntimeError("交易流水写入后未执行账本校验")
    return row, validated_replay


async def create_transaction_record(
    request: PortfolioTransactionCreate,
    user_id: int,
) -> tuple[dict, dict, LedgerReplay] | None:
    resolved = await _resolve_stock(request, user_id)
    if resolved is None:
        return None
    stock_name, quote = resolved

    row, replay = await call_blocking(
        _persist_transaction,
        request,
        user_id,
        stock_name,
        semaphore=database_semaphore,
    )
    return row, quote, replay


async def create_transaction(
    request: PortfolioTransactionCreate,
    user_id: int,
) -> PortfolioTransaction | None:
    created = await create_transaction_record(request, user_id)
    if created is None:
        return None
    row, _, replay = created
    transaction = next(item for item in replay.transactions if item.id == row["id"])
    return portfolio_builder.transaction_from_replay(transaction)


async def preview_transaction(
    request: PortfolioTransactionCreate,
    user_id: int,
) -> PortfolioTransactionPreview | None:
    resolved = await _resolve_stock(request, user_id)
    if resolved is None:
        return None
    stock_name, _ = resolved
    rows = await call_blocking(
        portfolio_store.list_transactions,
        user_id,
        stock_code=request.stock_code,
        semaphore=database_semaphore,
    )
    candidate_id = max((int(row["id"]) for row in rows), default=0) + 1
    trade_time = request.trade_time.isoformat(timespec="seconds")
    preview = portfolio_accounting.preview_transaction(
        rows,
        {
            "id": candidate_id,
            "user_id": user_id,
            "stock_code": request.stock_code,
            "stock_name": stock_name,
            "side": request.side,
            "trade_price": request.trade_price,
            "trade_time": trade_time,
            "shares": request.shares,
            "fee": request.fee,
            "note": request.note,
            "created_at": trade_time,
        },
    )
    return portfolio_builder.preview_from_replay(request, preview)


async def preview_transaction_update(
    transaction_id: int,
    request: PortfolioTransactionCreate,
    user_id: int,
) -> PortfolioTransactionPreview:
    existing = await call_blocking(
        portfolio_store.get_transaction,
        user_id,
        transaction_id,
        semaphore=database_semaphore,
    )
    if existing is None:
        raise PortfolioTransactionNotFoundError
    resolved = await _resolve_stock(request, user_id)
    if resolved is None:
        raise UnknownPortfolioStockError(request.stock_code)
    stock_name, _ = resolved

    previous_stock_code = str(existing["stock_code"])
    if previous_stock_code != request.stock_code:
        previous_rows = await call_blocking(
            portfolio_store.list_transactions,
            user_id,
            stock_code=previous_stock_code,
            semaphore=database_semaphore,
        )
        replay_transactions([row for row in previous_rows if int(row["id"]) != transaction_id])

    rows = await call_blocking(
        portfolio_store.list_transactions,
        user_id,
        stock_code=request.stock_code,
        semaphore=database_semaphore,
    )
    trade_time = request.trade_time.isoformat(timespec="seconds")
    preview = portfolio_accounting.preview_transaction(
        [row for row in rows if int(row["id"]) != transaction_id],
        {
            "id": transaction_id,
            "user_id": user_id,
            "stock_code": request.stock_code,
            "stock_name": stock_name,
            "side": request.side,
            "trade_price": request.trade_price,
            "trade_time": trade_time,
            "shares": request.shares,
            "fee": request.fee,
            "note": request.note,
            "created_at": str(existing.get("created_at") or trade_time),
        },
    )
    return portfolio_builder.preview_from_replay(request, preview)


def _persist_transaction_update(
    transaction_id: int,
    request: PortfolioTransactionCreate,
    user_id: int,
    stock_name: str,
) -> tuple[dict, LedgerReplay] | None:
    validated_replay: LedgerReplay | None = None

    def validate(rows: list[dict]) -> LedgerReplay:
        nonlocal validated_replay
        validated_replay = replay_transactions(rows)
        return validated_replay

    row = portfolio_store.update_transaction(
        user_id,
        transaction_id,
        request.stock_code,
        stock_name,
        request.side,
        request.trade_price,
        request.trade_time.isoformat(timespec="seconds"),
        request.shares,
        request.fee,
        request.note,
        validator=validate,
    )
    if row is None:
        return None
    if validated_replay is None:
        raise RuntimeError("交易流水更新后未执行账本校验")
    return row, validated_replay


async def update_transaction(
    transaction_id: int,
    request: PortfolioTransactionCreate,
    user_id: int,
) -> PortfolioTransaction:
    existing = await call_blocking(
        portfolio_store.get_transaction,
        user_id,
        transaction_id,
        semaphore=database_semaphore,
    )
    if existing is None:
        raise PortfolioTransactionNotFoundError
    resolved = await _resolve_stock(request, user_id)
    if resolved is None:
        raise UnknownPortfolioStockError(request.stock_code)
    stock_name, _ = resolved
    updated = await call_blocking(
        _persist_transaction_update,
        transaction_id,
        request,
        user_id,
        stock_name,
        semaphore=database_semaphore,
    )
    if updated is None:
        raise PortfolioTransactionNotFoundError
    row, replay = updated
    transaction = next(item for item in replay.transactions if item.id == row["id"])
    return portfolio_builder.transaction_from_replay(transaction)


async def delete_transaction(transaction_id: int, user_id: int) -> bool:
    return await call_blocking(
        portfolio_store.delete_transaction,
        user_id,
        transaction_id,
        validator=replay_transactions,
        semaphore=database_semaphore,
    )


__all__ = [
    "InsufficientSharesError",
    "PortfolioTransactionNotFoundError",
    "UnknownPortfolioStockError",
    "create_transaction_record",
    "create_transaction",
    "delete_transaction",
    "preview_transaction",
    "preview_transaction_update",
    "update_transaction",
]
