import asyncio
import logging

import pandas as pd

from app.services.providers.akshare import akshare_provider as _akshare_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.symbol_utils import normalize_code

logger = logging.getLogger(__name__)

_PERCENTILE_CONCURRENCY = 5
_percentile_semaphore = asyncio.Semaphore(_PERCENTILE_CONCURRENCY)
_percentile_inflight: dict[tuple[str, str, str], asyncio.Task[float | None]] = {}
_percentile_inflight_lock = asyncio.Lock()


def _percentile_key(code: str, indicator: str, period: str) -> tuple[str, str, str]:
    return normalize_code(code).raw, indicator, period


async def _compute_percentile(code: str, indicator: str = "市盈率(TTM)", period: str = "近三年") -> float | None:
    cache_key = dated_cache_key("percentile", code, indicator, period)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    sym = normalize_code(code)
    df = await call_blocking(
        _akshare_provider.fetch_stock_valuation_baidu,
        symbol=sym.raw,
        indicator=indicator,
        period=period,
    )

    if df.empty or len(df) < 2:
        return None

    val_col = df.columns[-1]
    series = pd.to_numeric(df[val_col], errors="coerce").dropna()
    if series.empty:
        return None

    current = series.iloc[-1]
    count_below = (series < current).sum()
    percentile = float(round(count_below / len(series) * 100, 1))
    cache.set(cache_key, percentile, ttl=86400)
    return percentile


async def _compute_percentile_limited(
    code: str,
    indicator: str,
    period: str,
) -> float | None:
    async with _percentile_semaphore:
        return await _compute_percentile(code, indicator, period)


async def _compute_percentile_inflight(
    code: str,
    indicator: str,
    period: str,
) -> float | None:
    key = _percentile_key(code, indicator, period)

    async with _percentile_inflight_lock:
        task = _percentile_inflight.get(key)
        if task is None:
            task = asyncio.create_task(_compute_percentile_limited(key[0], indicator, period))
            _percentile_inflight[key] = task

    try:
        return await task
    finally:
        if task.done():
            async with _percentile_inflight_lock:
                if _percentile_inflight.get(key) is task:
                    _percentile_inflight.pop(key, None)


async def compute_percentiles(codes: list[str], indicator: str = "市盈率(TTM)", period: str = "近三年") -> list[dict]:
    unique_codes: dict[tuple[str, str, str], str] = {}
    ordered_keys: list[tuple[str, str, str]] = []
    code_keys: list[tuple[str, str, str]] = []

    for code in codes:
        key = _percentile_key(code, indicator, period)
        code_keys.append(key)
        if key not in unique_codes:
            unique_codes[key] = code
            ordered_keys.append(key)

    async def compute_one(key: tuple[str, str, str], original_code: str) -> tuple[tuple[str, str, str], float | None]:
        try:
            return key, await _compute_percentile_inflight(original_code, indicator, period)
        except Exception as e:
            logger.warning(f"计算估值百分位失败: {original_code}, {e}")
            return key, None

    pairs = await asyncio.gather(
        *(compute_one(key, unique_codes[key]) for key in ordered_keys)
    )
    percentile_by_key = dict(pairs)

    return [
        {"code": code, "percentile": percentile_by_key.get(key)}
        for code, key in zip(codes, code_keys)
    ]
