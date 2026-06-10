import asyncio
import logging

import pandas as pd

from app.models.stock import IntradayData, IntradayItem
from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.singleflight import AsyncSingleFlight
from app.utils.symbol_utils import normalize_code
from app.utils.market_utils import get_last_trade_date
from app.utils.data_clean import safe_float

logger = logging.getLogger(__name__)

_intraday_singleflight = AsyncSingleFlight[IntradayData]()


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


def _get_sina_provider():
    """Lazily resolve the Sina provider singleton."""
    return get_provider("sina")


async def _safe_fetch_intraday(source_name: str, fetcher, code: str, date: str | None = None) -> pd.DataFrame:
    """安全调用分时数据获取，异常时返回空 DataFrame。

    Param:
        source_name: 数据源名称用于日志
        fetcher: 同步获取函数
        code: 股票代码
        date: 交易日期
    Return:
        分时数据 DataFrame，异常时为空
    """
    try:
        return await call_blocking(fetcher, code=code, date=date)
    except Exception as exc:
        logger.info(f"{source_name}分时数据不可用，尝试下一数据源: code={code}, error={exc}")
        return pd.DataFrame()


async def _load_intraday(sym, date: str | None) -> IntradayData:
    """并发调用多个数据源加载并组装分时数据。

    Param:
        sym: 归一化后的代码对象
        date: 交易日期
    Return:
        IntradayData 模型对象
    """
    fetchers = [
        ("新浪财经分钟直连", _get_sina_provider().fetch_stock_intraday_minute_direct),
        ("Akshare新浪分钟", _get_akshare_provider().fetch_stock_intraday_minute_sina),
        ("东方财富分钟直连", _get_eastmoney_provider().fetch_stock_intraday_minute),
        ("Akshare东方财富分钟K线", _get_akshare_provider().fetch_stock_intraday_minute),
        ("Akshare东方财富逐笔成交", _get_akshare_provider().fetch_stock_intraday_transactions),
        ("东方财富逐笔直连", _get_eastmoney_provider().fetch_stock_intraday_transactions),
    ]

    tasks = [_safe_fetch_intraday(name, fn, sym.raw, date) for name, fn in fetchers]
    results = await asyncio.gather(*tasks)

    df = pd.DataFrame()
    for result in results:
        if not result.empty:
            df = result
            break

    if df.empty:
        return IntradayData(code=sym.raw, prev_close=None, items=[])

    df = df.copy()
    df["time"] = df["time"].map(lambda value: str(value).strip())
    df = df[df["time"] != ""]
    df = df.sort_values("time")

    prev_close = None
    first_price = safe_float(df.iloc[0].get("price")) if not df.empty else None
    first_change_pct = safe_float(df.iloc[0].get("change_pct")) if not df.empty else None
    if first_price not in (None, 0) and first_change_pct is not None:
        prev_close = round(first_price / (1 + first_change_pct / 100), 4)
    elif first_price is not None:
        prev_close = first_price

    items: list[IntradayItem] = []
    for _, row in df.iterrows():
        price = safe_float(row.get("price"))
        if price is None:
            continue
        change_pct = safe_float(row.get("change_pct"))
        if change_pct is None and prev_close not in (None, 0):
            change_pct = round((price - prev_close) / prev_close * 100, 2)
        items.append(
            IntradayItem(
                time=str(row.get("time", "")),
                price=price,
                avg_price=safe_float(row.get("avg_price")),
                volume=safe_float(row.get("volume")),
                amount=safe_float(row.get("amount")),
                change_pct=change_pct,
            )
        )

    return IntradayData(code=sym.raw, prev_close=prev_close, items=items)


async def get_intraday(code: str) -> IntradayData:
    """获取股票分时数据，带 single-flight 与 5 分钟缓存。

    Param:
        code: 股票代码
    Return:
        IntradayData 模型对象，包含逐分钟成交点
    """
    sym = normalize_code(code)
    date = get_last_trade_date(code)
    cache_key = dated_cache_key("intraday", sym.raw, date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    async def load_and_cache() -> IntradayData:
        """加载分时数据并写入缓存。

        Param:
            无
        Return:
            IntradayData 模型对象
        """
        result = await _load_intraday(sym, date)
        cache.set(cache_key, result, ttl=300)
        return result

    return await _intraday_singleflight.do(cache_key, load_and_cache)
