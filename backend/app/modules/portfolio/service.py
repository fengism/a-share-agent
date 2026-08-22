import app.modules.portfolio.builder as portfolio_builder
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.infrastructure.persistence import portfolio as portfolio_store
from app.modules.portfolio.accounting import replay_transactions
from app.modules.portfolio.quotes import fetch_quote_batch
from app.modules.portfolio.schemas import PortfolioResponse


async def get_portfolio(user_id: int) -> PortfolioResponse:
    rows = await call_blocking(
        portfolio_store.list_transactions,
        user_id,
        semaphore=database_semaphore,
    )
    replay = replay_transactions(rows)
    quote_batch = await fetch_quote_batch([lot.stock_code for lot in replay.open_lots])
    return portfolio_builder.build_portfolio(
        replay,
        quote_batch.quotes,
        quoted_at=quote_batch.quoted_at,
        quote_source=quote_batch.source,
        quote_stale=quote_batch.stale,
    )


__all__ = ["get_portfolio"]
