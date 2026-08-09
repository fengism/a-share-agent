"""Provider-backed stock risk datasets."""

import asyncio
from typing import Any

from app.core.concurrency.rate_limiter import call_blocking, eastmoney_semaphore
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider


async def get_stock_risk_data(code: str) -> dict[str, Any]:
    provider = get_provider("eastmoney")
    fund_flow, margin, block, holder = await asyncio.gather(
        provider_gateway.call(
            "eastmoney",
            "stock_fund_flow",
            lambda: call_blocking(
                provider.fetch_stock_fund_flow,
                code,
                semaphore=eastmoney_semaphore,
            ),
        ),
        provider_gateway.call(
            "eastmoney",
            "margin_trading",
            lambda: call_blocking(
                provider.fetch_margin_trading,
                code,
                semaphore=eastmoney_semaphore,
            ),
        ),
        provider_gateway.call(
            "eastmoney",
            "block_trade",
            lambda: call_blocking(
                provider.fetch_block_trade,
                code,
                semaphore=eastmoney_semaphore,
            ),
        ),
        provider_gateway.call(
            "eastmoney",
            "holder_num_change",
            lambda: call_blocking(
                provider.fetch_holder_num_change,
                code,
                semaphore=eastmoney_semaphore,
            ),
        ),
    )
    return {
        "fund_flow": fund_flow[-30:] if fund_flow else [],
        "margin_trading": margin[:10] if margin else [],
        "block_trade": block[:10] if block else [],
        "holder_change": holder[:4] if holder else [],
    }
