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
    """构造估值百分位单飞键。

    Param:
        code: 股票代码
        indicator: 估值指标名（如市盈率TTM）
        period: 时间区间标识
    Return:
        归一化代码与参数组合的三元组
    """
    return normalize_code(code).raw, indicator, period


async def _compute_percentile(code: str, indicator: str = "市盈率(TTM)", period: str = "近三年") -> float | None:
    """计算单个股票的估值百分位，带 1 天缓存。

    Param:
        code: 股票代码
        indicator: 估值指标名
        period: 时间区间标识
    Return:
        百分位浮点数（0-100），数据不足时返回 None
    """
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
    """带信号量限流的百分位计算包装。

    Param:
        code: 股票代码
        indicator: 估值指标名
        period: 时间区间标识
    Return:
        百分位浮点数，数据不足时返回 None
    """
    async with _percentile_semaphore:
        return await _compute_percentile(code, indicator, period)


async def _compute_percentile_inflight(
    code: str,
    indicator: str,
    period: str,
) -> float | None:
    """复用同一参数的进行中任务，避免重复计算。

    Param:
        code: 股票代码
        indicator: 估值指标名
        period: 时间区间标识
    Return:
        百分位浮点数，数据不足时返回 None
    """
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
    """批量计算多个股票的估值百分位，自动去重并并发限流。

    Param:
        codes: 股票代码列表（允许重复）
        indicator: 估值指标名
        period: 时间区间标识
    Return:
        与输入顺序对齐的 {"code", "percentile"} 字典列表
    """
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
        """计算单个键的百分位并返回原键，捕获异常。

        Param:
            key: 百分位计算键三元组
            original_code: 原始股票代码
        Return:
            (键, 百分位) 元组，计算失败时百分位为 None
        """
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
