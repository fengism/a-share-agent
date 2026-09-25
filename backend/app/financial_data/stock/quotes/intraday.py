"""个股分时行情服务。"""

import asyncio
import logging
from typing import cast

import pandas as pd

from app.core.cache import dated_cache_key, series_cache
from app.core.cache_policies import STOCK_INTRADAY
from app.core.concurrency.rate_limiter import call_blocking, cls_semaphore, sina_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import normalize_code, safe_float
from app.financial_data.stock.quotes.schemas import IntradayData, IntradayItem
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_intraday_singleflight: AsyncSingleFlight[IntradayData] = AsyncSingleFlight()
_TRADE_DATE_TIMEOUT_SECONDS = 0.75
_DIRECT_SOURCE_TIMEOUT_SECONDS = 1.5
_SECONDARY_SOURCE_TIMEOUT_SECONDS = 1.0
_FALLBACK_SOURCE_TIMEOUT_SECONDS = 1.0


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


def _get_cls_provider():
    """Lazily resolve the CLS provider singleton."""
    return get_provider("cls")


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
        provider_name = "eastmoney"
        semaphore = None
        if source_name.startswith("新浪"):
            provider_name = "sina"
        elif source_name.startswith("财联社"):
            provider_name = "cls"
            semaphore = cls_semaphore
        elif source_name.startswith("Akshare"):
            provider_name = "akshare"
        return await provider_gateway.call(
            provider_name,
            "stock_intraday",
            lambda: call_blocking(fetcher, code=code, date=date, semaphore=semaphore),
            max_attempts=1,
        )
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
    async def first_nonempty(fetchers, timeout_seconds: float) -> tuple[str, pd.DataFrame] | None:
        tasks = [
            asyncio.create_task(_safe_fetch_intraday(name, fetcher, sym.raw, date))
            for name, fetcher in fetchers
        ]
        task_order = {task: index for index, task in enumerate(tasks)}
        pending = set(tasks)
        try:
            async with asyncio.timeout(timeout_seconds):
                while pending:
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    for task in sorted(done, key=task_order.__getitem__):
                        frame = task.result()
                        if not frame.empty:
                            index = task_order[task]
                            return fetchers[index][0], frame
        except TimeoutError:
            return None
        finally:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        return None

    groups = [
        (
            [
                ("新浪财经分钟直连", _get_sina_provider().fetch_stock_intraday_minute_direct),
                ("财联社分钟直连", _get_cls_provider().fetch_stock_intraday_minute),
            ],
            _DIRECT_SOURCE_TIMEOUT_SECONDS,
        ),
        (
            [("Akshare新浪分钟", _get_akshare_provider().fetch_stock_intraday_minute_sina)],
            _SECONDARY_SOURCE_TIMEOUT_SECONDS,
        ),
        (
            [
                ("东方财富分钟直连（fallback）", _get_eastmoney_provider().fetch_stock_intraday_minute),
                ("Akshare东方财富分钟K线（fallback）", _get_akshare_provider().fetch_stock_intraday_minute),
                ("Akshare东方财富逐笔成交（fallback）", _get_akshare_provider().fetch_stock_intraday_transactions),
                ("东方财富逐笔直连（fallback）", _get_eastmoney_provider().fetch_stock_intraday_transactions),
            ],
            _FALLBACK_SOURCE_TIMEOUT_SECONDS,
        ),
    ]

    selected_source = ""
    df = pd.DataFrame()
    for fetchers, timeout_seconds in groups:
        selected = await first_nonempty(fetchers, timeout_seconds)
        if selected is not None:
            selected_source, df = selected
            break

    if df.empty:
        return IntradayData(code=sym.raw, source="", prev_close=None, items=[])

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

    return IntradayData(code=sym.raw, source=selected_source, prev_close=prev_close, items=items)


async def get_intraday(code: str) -> IntradayData:
    """获取股票分时数据，带 single-flight 与 30 秒缓存。

    Param:
        code: 股票代码
    Return:
        IntradayData 模型对象，包含逐分钟成交点
    """
    sym = normalize_code(code)
    try:
        date = await asyncio.wait_for(
            provider_gateway.call_blocking(
                "sina",
                "fetch_last_trade_date",
                get_provider("sina").fetch_last_trade_date,
                code,
                semaphore=sina_semaphore,
                max_attempts=1,
            ),
            timeout=_TRADE_DATE_TIMEOUT_SECONDS,
        )
    except Exception as error:
        err_detail = type(error).__name__ if not str(error) else str(error)
        logger.debug("最近交易日探活跳过 (%s)，分时源将自行确定最新交易日: code=%s", err_detail, sym.raw)
        date = ""
    cache_key = dated_cache_key("intraday", sym.raw, date)
    cached = series_cache.get(cache_key)
    if isinstance(cached, IntradayData):
        return cached

    async def load_and_cache() -> IntradayData:
        """加载分时数据并写入缓存。

        Param:
            无
        Return:
            IntradayData 模型对象
        """
        result = await _load_intraday(sym, date)
        series_cache.set(cache_key, result, ttl=STOCK_INTRADAY.ttl_seconds)
        return result

    return cast(IntradayData, await _intraday_singleflight.do(cache_key, load_and_cache))
