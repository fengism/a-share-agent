"""可复现量化计算使用的严格历史行情。"""

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.contracts.market import KlineItem
from app.core.concurrency.rate_limiter import akshare_semaphore, call_blocking, tencent_semaphore
from app.core.market import normalize_code, safe_float
from app.infrastructure.providers.provider_chain import BaseProviderChain, ProviderAttempt
from app.infrastructure.providers.registry import get_provider


@dataclass(frozen=True)
class HistoricalBarSet:
    code: str
    period: str
    adjust: str
    source: str
    adjustment_verified: bool
    data_hash: str
    items: list[KlineItem]


def _column_value(row: pd.Series, *names: str):
    for name in names:
        if name in row:
            return row.get(name)
    return None


def _normalize_frame(code: str, frame: pd.DataFrame) -> list[KlineItem]:
    items: list[KlineItem] = []
    for _, row in frame.iterrows():
        raw_date = _column_value(row, "日期", "date")
        open_price = safe_float(_column_value(row, "开盘", "open"))
        close_price = safe_float(_column_value(row, "收盘", "close"))
        high_price = safe_float(_column_value(row, "最高", "high"))
        low_price = safe_float(_column_value(row, "最低", "low"))
        if raw_date is None or None in (open_price, close_price, high_price, low_price):
            continue
        parsed_date = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_date):
            continue
        items.append(
            KlineItem(
                code=code,
                date=parsed_date.strftime("%Y-%m-%d"),
                open=open_price,
                close=close_price,
                high=high_price,
                low=low_price,
                volume=safe_float(_column_value(row, "成交量", "volume")) or 0,
                amount=safe_float(_column_value(row, "成交额", "amount")) or 0,
                amplitude=safe_float(_column_value(row, "振幅", "amplitude")),
                turnover_pct=safe_float(_column_value(row, "换手率", "turnover_pct")),
                change_pct=safe_float(_column_value(row, "涨跌幅", "change_pct")),
                pre_close=safe_float(_column_value(row, "昨收", "pre_close")),
            )
        )
    return sorted({item.date: item for item in items}.values(), key=lambda item: item.date)


def historical_bar_hash(code: str, period: str, adjust: str, items: list[KlineItem]) -> str:
    payload = {
        "code": code,
        "period": period,
        "adjust": adjust,
        "items": [item.model_dump(mode="json") for item in items],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


async def _load_historical_source(
    source: str,
    symbol: str,
    fetcher: Callable[..., pd.DataFrame],
    *fetch_args: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, list[KlineItem]]:
    frame = await call_blocking(fetcher, *fetch_args, semaphore=semaphore)
    items = _normalize_frame(symbol, frame)
    if not items:
        raise ValueError(f"{source} 未返回有效历史行情")
    return source, items


def _historical_source_attempts(
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
    adjust: str,
) -> list[ProviderAttempt]:
    attempts = [
        ProviderAttempt(
            label="AkShare 东方财富复权K线",
            loader=lambda: _load_historical_source(
                "akshare-eastmoney",
                symbol,
                get_provider("akshare").fetch_stock_kline,
                symbol,
                period,
                start_date,
                end_date,
                adjust,
                semaphore=akshare_semaphore,
            ),
            on_error=f"东方财富复权K线不可用: code={symbol}",
        )
    ]
    if period == "daily":
        attempts.append(
            ProviderAttempt(
                label="腾讯财经复权K线",
                loader=lambda: _load_historical_source(
                    "tencent",
                    symbol,
                    get_provider("tencent").fetch_stock_kline,
                    symbol,
                    start_date,
                    end_date,
                    adjust,
                    semaphore=tencent_semaphore,
                ),
                on_error=f"腾讯财经复权K线不可用: code={symbol}",
            )
        )
        attempts.append(
            ProviderAttempt(
                label="AkShare 新浪复权K线",
                loader=lambda: _load_historical_source(
                    "akshare-sina",
                    symbol,
                    get_provider("akshare").fetch_stock_kline_sina,
                    symbol,
                    start_date,
                    end_date,
                    adjust,
                    semaphore=akshare_semaphore,
                ),
                on_error=f"新浪复权K线不可用: code={symbol}",
            )
        )
    return attempts


async def get_historical_bars(
    code: str,
    start_date: date,
    end_date: date,
    *,
    period: str = "daily",
    adjust: str = "qfq",
) -> HistoricalBarSet:
    """通过支持显式复权的 Provider Chain 加载历史行情。"""
    symbol = normalize_code(code).raw
    if period not in {"daily", "weekly", "monthly"}:
        raise ValueError("不支持的 K 线周期")
    if adjust not in {"qfq", "hfq", ""}:
        raise ValueError("不支持的复权方式")
    attempts = _historical_source_attempts(
        symbol,
        period,
        start_date.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d"),
        adjust,
    )
    try:
        source, items = await BaseProviderChain(
            attempts,
            operation="strict_stock_history",
        ).run()
    except Exception as error:
        attempted_sources = "、".join(attempt.label for attempt in attempts)
        raise RuntimeError(f"无法获取 {symbol} 的严格历史行情；已尝试 {attempted_sources}，请稍后重试") from error
    return HistoricalBarSet(
        code=symbol,
        period=period,
        adjust=adjust,
        source=source,
        adjustment_verified=True,
        data_hash=historical_bar_hash(symbol, period, adjust, items),
        items=items,
    )
