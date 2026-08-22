import app.modules.portfolio.builder as portfolio_builder
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.infrastructure.persistence import portfolio as portfolio_store
from app.modules.portfolio.accounting import replay_transactions
from app.modules.portfolio.schemas import (
    PortfolioPosition,
    PortfolioPositionCreate,
    PortfolioTransactionCreate,
)
from app.modules.portfolio.transactions import create_transaction_record, delete_transaction


async def list_held_stock_codes(user_id: int) -> list[str]:
    rows = await call_blocking(
        portfolio_store.list_transactions,
        user_id,
        semaphore=database_semaphore,
    )
    return list(dict.fromkeys(lot.stock_code for lot in replay_transactions(rows).open_lots))


async def add_position(request: PortfolioPositionCreate, user_id: int) -> PortfolioPosition | None:
    transaction_request = PortfolioTransactionCreate(
        stock_code=request.stock_code,
        side="buy",
        trade_price=request.buy_price,
        trade_time=request.buy_time,
        shares=request.shares,
    )
    created = await create_transaction_record(transaction_request, user_id)
    if created is None:
        return None
    row, quote, _ = created
    return portfolio_builder.position_from_transaction(row, quote)


async def delete_position(position_id: int, user_id: int) -> bool:
    transaction = await call_blocking(
        portfolio_store.get_transaction,
        user_id,
        position_id,
        semaphore=database_semaphore,
    )
    if transaction is None or transaction["side"] != "buy":
        return False
    return await delete_transaction(position_id, user_id)


__all__ = ["add_position", "delete_position", "list_held_stock_codes"]
