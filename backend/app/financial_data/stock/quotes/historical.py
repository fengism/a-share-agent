"""可复现量化计算使用的严格历史行情。"""

import asyncio
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.configuration import get_settings
from app.core.concurrency.rate_limiter import (
    akshare_semaphore,
    call_blocking,
    cls_semaphore,
    eastmoney_semaphore,
    tdx_semaphore,
    tencent_semaphore,
)
from app.core.exceptions import UpstreamUnavailableError
from app.core.market import normalize_code, safe_float
from app.domain.market import KlineItem
from app.financial_data.kline_quality import validate_kline_frame
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


def _frame_column(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return frame[name]
    return pd.Series(index=frame.index, dtype="object")


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
    normalized_items = sorted({item.date: item for item in items}.values(), key=lambda item: item.date)
    for index in range(1, len(normalized_items)):
        current = normalized_items[index]
        previous = normalized_items[index - 1]
        if current.pre_close is None:
            current.pre_close = previous.close
        if current.change_pct is None and previous.close != 0:
            current.change_pct = round((current.close - previous.close) / previous.close * 100, 2)
    return normalized_items


def historical_bar_hash(code: str, period: str, adjust: str, items: list[KlineItem]) -> str:
    payload = {
        "code": code,
        "period": period,
        "adjust": adjust,
        "items": [item.model_dump(mode="json") for item in items],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _resample_adjusted_daily_frame(frame: pd.DataFrame, period: str) -> pd.DataFrame:
    """Aggregate adjusted daily bars without inventing non-trading period-end dates."""
    frequency = {"weekly": "W-FRI", "monthly": "M"}.get(period)
    if frequency is None:
        raise ValueError(f"不支持从日线聚合为 {period}")

    columns = {
        "日期": _frame_column(frame, "日期", "date"),
        "开盘": _frame_column(frame, "开盘", "open"),
        "收盘": _frame_column(frame, "收盘", "close"),
        "最高": _frame_column(frame, "最高", "high"),
        "最低": _frame_column(frame, "最低", "low"),
        "成交量": _frame_column(frame, "成交量", "volume"),
        "成交额": _frame_column(frame, "成交额", "amount"),
        "换手率": _frame_column(frame, "换手率", "turnover_pct"),
    }
    normalized = pd.DataFrame(columns)
    normalized["日期"] = pd.to_datetime(normalized["日期"], errors="coerce")
    for column in ("开盘", "收盘", "最高", "最低", "成交量", "成交额", "换手率"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    valid = (
        normalized["日期"].notna()
        & (normalized["开盘"] > 0)
        & (normalized["收盘"] > 0)
        & (normalized["最高"] >= normalized[["开盘", "收盘"]].max(axis=1))
        & (normalized["最低"] > 0)
        & (normalized["最低"] <= normalized[["开盘", "收盘"]].min(axis=1))
    )
    normalized = (
        normalized.loc[valid]
        .sort_values("日期")
        .drop_duplicates(subset=["日期"], keep="last")
    )
    if normalized.empty:
        return normalized.drop(columns=["换手率"], errors="ignore")

    normalized["_period"] = normalized["日期"].dt.to_period(frequency)
    records: list[dict[str, object]] = []
    for _, group in normalized.groupby("_period", sort=True, observed=True):
        record: dict[str, object] = {
            "日期": group["日期"].iloc[-1].strftime("%Y-%m-%d"),
            "开盘": float(group["开盘"].iloc[0]),
            "收盘": float(group["收盘"].iloc[-1]),
            "最高": float(group["最高"].max()),
            "最低": float(group["最低"].min()),
            "成交量": float(group["成交量"].sum(min_count=1)),
            "成交额": float(group["成交额"].sum(min_count=1)),
        }
        if group["换手率"].notna().any():
            record["换手率"] = float(group["换手率"].sum(min_count=1))
        records.append(record)
    return pd.DataFrame(records)


async def _load_historical_source(
    source: str,
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
    fetcher: Callable[..., pd.DataFrame],
    *fetch_args: object,
    semaphore: asyncio.Semaphore,
    aggregate_period: str | None = None,
    require_turnover: bool = False,
) -> tuple[str, list[KlineItem]]:
    frame = await call_blocking(fetcher, *fetch_args, semaphore=semaphore)
    if aggregate_period is not None:
        frame = _resample_adjusted_daily_frame(frame, aggregate_period)
    frame = validate_kline_frame(
        source,
        frame,
        start_date=start_date,
        end_date=end_date,
        period=period,
    )
    items = _normalize_frame(symbol, frame)
    if not items:
        raise ValueError(f"{source} 未返回有效历史行情")
    if require_turnover:
        valid_turnover = [
            item.turnover_pct is not None
            and math.isfinite(item.turnover_pct)
            and item.turnover_pct >= 0
            for item in items
        ]
        valid_count = sum(valid_turnover)
        if valid_count == 0:
            raise ValueError(f"{source} 未返回有效换手率")
        coverage = valid_count / len(items)
        if coverage < 0.95:
            raise ValueError(f"{source} 换手率覆盖率不足: {coverage:.1%}")
        first_valid_index = valid_turnover.index(True)
        if not all(valid_turnover[first_valid_index:]):
            raise ValueError(f"{source} 换手率存在缺口")
    return source, items


def _historical_source_attempts(
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
    adjust: str,
    require_turnover: bool = False,
) -> list[ProviderAttempt[tuple[str, list[KlineItem]]]]:
    attempts: list[ProviderAttempt[tuple[str, list[KlineItem]]]] = []
    if period == "daily":
        if get_settings().tdx_http_enabled:
            attempts.append(
                ProviderAttempt(
                    label="TDX HTTP 复权K线",
                    loader=lambda: _load_historical_source(
                        "tdx_http",
                        symbol,
                        period,
                        start_date,
                        end_date,
                        get_provider("tdx_http").fetch_stock_kline,
                        symbol,
                        start_date,
                        end_date,
                        adjust,
                        require_turnover,
                        semaphore=tdx_semaphore,
                        require_turnover=require_turnover,
                    ),
                    on_error=f"TDX HTTP 复权K线不可用: code={symbol}",
                    max_attempts=1,
                )
            )
        attempts.append(
            ProviderAttempt(
                label="腾讯财经复权K线",
                loader=lambda: _load_historical_source(
                    "tencent",
                    symbol,
                    period,
                    start_date,
                    end_date,
                    get_provider("tencent").fetch_stock_kline,
                    symbol,
                    start_date,
                    end_date,
                    adjust,
                    semaphore=tencent_semaphore,
                    require_turnover=require_turnover,
                ),
                on_error=f"腾讯财经复权K线不可用: code={symbol}",
                max_attempts=1,
            )
        )
        attempts.append(
            ProviderAttempt(
                label="AkShare 新浪复权K线",
                loader=lambda: _load_historical_source(
                    "akshare-sina",
                    symbol,
                    period,
                    start_date,
                    end_date,
                    get_provider("akshare").fetch_stock_kline_sina,
                    symbol,
                    start_date,
                    end_date,
                    adjust,
                    semaphore=akshare_semaphore,
                    require_turnover=require_turnover,
                ),
                on_error=f"新浪复权K线不可用: code={symbol}",
                max_attempts=1,
            )
        )
    else:
        period_label = "周" if period == "weekly" else "月"
        if get_settings().tdx_http_enabled:
            attempts.append(
                ProviderAttempt(
                    label=f"TDX HTTP 日线聚合复权{period_label}K线",
                    loader=lambda: _load_historical_source(
                        "tdx-http-daily-aggregate",
                        symbol,
                        period,
                        start_date,
                        end_date,
                        get_provider("tdx_http").fetch_stock_kline,
                        symbol,
                        start_date,
                        end_date,
                        adjust,
                        require_turnover,
                        semaphore=tdx_semaphore,
                        aggregate_period=period,
                        require_turnover=require_turnover,
                    ),
                    on_error=f"TDX HTTP 日线聚合复权{period_label}K线不可用: code={symbol}",
                    max_attempts=1,
                )
            )
        attempts.extend([
            ProviderAttempt(
                label=f"腾讯财经日线聚合复权{period_label}K线",
                loader=lambda: _load_historical_source(
                    "tencent-daily-aggregate",
                    symbol,
                    period,
                    start_date,
                    end_date,
                    get_provider("tencent").fetch_stock_kline,
                    symbol,
                    start_date,
                    end_date,
                    adjust,
                    semaphore=tencent_semaphore,
                    aggregate_period=period,
                    require_turnover=require_turnover,
                ),
                on_error=f"腾讯财经日线聚合复权{period_label}K线不可用: code={symbol}",
                max_attempts=1,
            ),
            ProviderAttempt(
                label=f"AkShare 新浪日线聚合复权{period_label}K线",
                loader=lambda: _load_historical_source(
                    "akshare-sina-daily-aggregate",
                    symbol,
                    period,
                    start_date,
                    end_date,
                    get_provider("akshare").fetch_stock_kline_sina,
                    symbol,
                    start_date,
                    end_date,
                    adjust,
                    semaphore=akshare_semaphore,
                    aggregate_period=period,
                    require_turnover=require_turnover,
                ),
                on_error=f"新浪日线聚合复权{period_label}K线不可用: code={symbol}",
                max_attempts=1,
            ),
        ])
    if adjust == "":
        attempts.append(
            ProviderAttempt(
                label="财联社不复权K线",
                loader=lambda: _load_historical_source(
                    "cls",
                    symbol,
                    period,
                    start_date,
                    end_date,
                    get_provider("cls").fetch_stock_kline,
                    symbol,
                    period,
                    start_date,
                    end_date,
                    adjust,
                    semaphore=cls_semaphore,
                    require_turnover=require_turnover,
                ),
                on_error=f"财联社不复权K线不可用: code={symbol}",
                max_attempts=1,
            )
        )
    attempts.extend([
        ProviderAttempt(
            label="东方财富复权K线直连（fallback）",
            loader=lambda: _load_historical_source(
                "eastmoney-direct-fallback",
                symbol,
                period,
                start_date,
                end_date,
                get_provider("eastmoney").fetch_kline,
                symbol,
                period,
                start_date,
                end_date,
                adjust,
                semaphore=eastmoney_semaphore,
                require_turnover=require_turnover,
            ),
            on_error=f"东方财富直连复权K线 fallback 不可用: code={symbol}",
            max_attempts=1,
        ),
        ProviderAttempt(
            label="AkShare 东方财富复权K线（fallback）",
            loader=lambda: _load_historical_source(
                "akshare-eastmoney-fallback",
                symbol,
                period,
                start_date,
                end_date,
                get_provider("akshare").fetch_stock_kline,
                symbol,
                period,
                start_date,
                end_date,
                adjust,
                semaphore=akshare_semaphore,
                require_turnover=require_turnover,
            ),
            on_error=f"AkShare 东方财富复权K线最终 fallback 不可用: code={symbol}",
            max_attempts=1,
        ),
    ])
    return attempts


async def get_historical_bars(
    code: str,
    start_date: date,
    end_date: date,
    *,
    period: str = "daily",
    adjust: str = "qfq",
    require_turnover: bool = False,
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
        require_turnover,
    )
    try:
        source, items = await BaseProviderChain(
            attempts,
            operation="strict_stock_history",
        ).run()
    except Exception as error:
        attempted_sources = "、".join(attempt.label for attempt in attempts)
        raise UpstreamUnavailableError(
            f"{symbol} 历史行情上游暂时不可用；已尝试 {attempted_sources}"
        ) from error
    return HistoricalBarSet(
        code=symbol,
        period=period,
        adjust=adjust,
        source=source,
        adjustment_verified=True,
        data_hash=historical_bar_hash(symbol, period, adjust, items),
        items=items,
    )
