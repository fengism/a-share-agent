import asyncio

import app.modules.portfolio.builder as portfolio_builder
from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.infrastructure.persistence import portfolio as portfolio_store
from app.modules.industry_classification.public import get_records_by_stock_codes
from app.modules.portfolio.accounting import replay_transactions
from app.modules.portfolio.quotes import fetch_quote_batch
from app.modules.portfolio.schemas import (
    PortfolioAccountSettings,
    PortfolioAccountSettingsUpdate,
    PortfolioResponse,
)


async def get_portfolio(user_id: int) -> PortfolioResponse:
    rows = await call_blocking(
        portfolio_store.list_transactions,
        user_id,
        semaphore=database_semaphore,
    )
    replay = replay_transactions(rows)
    stock_codes = list(dict.fromkeys(lot.stock_code for lot in replay.open_lots))
    quote_batch, settings, industries = await asyncio.gather(
        fetch_quote_batch(stock_codes),
        call_blocking(portfolio_store.get_account_settings, user_id, semaphore=database_semaphore),
        call_blocking(get_records_by_stock_codes, stock_codes, semaphore=database_semaphore),
    )
    return portfolio_builder.build_portfolio(
        replay,
        quote_batch.quotes,
        quoted_at=quote_batch.quoted_at,
        quote_source=quote_batch.source,
        quote_stale=quote_batch.stale,
        settings=settings,
        industries=industries,
    )


async def update_account_settings(
    request: PortfolioAccountSettingsUpdate,
    user_id: int,
) -> PortfolioAccountSettings:
    row = await call_blocking(
        portfolio_store.upsert_account_settings,
        user_id,
        **request.model_dump(),
        semaphore=database_semaphore,
    )
    return PortfolioAccountSettings.model_validate(row)


__all__ = ["get_portfolio", "update_account_settings"]
