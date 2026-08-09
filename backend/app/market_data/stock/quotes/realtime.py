"""Realtime stock quote access independent of product use cases."""

from app.core.concurrency.rate_limiter import tencent_semaphore
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider


async def fetch_realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """批量获取标准化实时行情。"""
    if not codes:
        return {}
    return await provider_gateway.call_blocking(
        "tencent",
        "stock_quotes",
        get_provider("tencent").fetch_stock_quotes,
        codes,
        semaphore=tencent_semaphore,
    )
