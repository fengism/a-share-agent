"""Merged official stock master for SSE, SZSE, and BSE listed companies."""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, cast

import pandas as pd

from app.configuration.paths import DATA_DIR
from app.core.cache import reference_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, exchange_semaphore, misc_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import safe_float, safe_string
from app.financial_data.stock.profile.industry_normalization import normalize_exchange_industry
from app.financial_data.stock.profile.merger import format_listing_date
from app.financial_data.stock.profile.sources import (
    BSE_STOCK_LISTING,
    SSE_STOCK_LISTING,
    SZSE_STOCK_LISTING,
    BasicDataSourceSpec,
)
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_EXCHANGES = ("SH", "SZ", "BJ")
_MASTER_CACHE_KEY = "official_exchange_stock_master:v1"
_MASTER_CACHE_TTL_SECONDS = 24 * 60 * 60
_MASTER_RETRY_TTL_SECONDS = 5 * 60
_MASTER_SNAPSHOT_MAX_STALE_SECONDS = 7 * 24 * 60 * 60
_MASTER_SNAPSHOT_PATH = DATA_DIR / "official_exchange_stock_master.json"
_MIN_EXCHANGE_RECORDS = {"SH": 1_000, "SZ": 1_000, "BJ": 100}


@dataclass(frozen=True)
class ExchangeStockRecord:
    code: str
    name: str
    exchange: str
    board: str | None
    industry: str | None
    listing_date: str | None
    total_shares: float | None
    circulating_shares: float | None
    source: str


@dataclass(frozen=True)
class ExchangeStockMaster:
    records: list[ExchangeStockRecord]
    failed_exchanges: dict[str, str]
    stale_exchanges: list[str]
    fetched_at: dict[str, float] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        available = {record.exchange for record in self.records}
        return all(exchange in available for exchange in _EXCHANGES)

    @property
    def name_map(self) -> dict[str, str]:
        return {record.code: record.name for record in self.records}


@dataclass(frozen=True)
class _PersistedExchangeSlice:
    fetched_at: float
    records: list[ExchangeStockRecord]


_master_singleflight: AsyncSingleFlight[ExchangeStockMaster] = AsyncSingleFlight()


def _get_exchange_provider():
    return get_provider("exchange")


def _source_for(exchange: str) -> BasicDataSourceSpec:
    return {"SH": SSE_STOCK_LISTING, "SZ": SZSE_STOCK_LISTING, "BJ": BSE_STOCK_LISTING}[exchange]


def _fetcher_for(exchange: str):
    provider = _get_exchange_provider()
    return {
        "SH": provider.fetch_stock_names_sh,
        "SZ": provider.fetch_stock_names_sz,
        "BJ": provider.fetch_stock_names_bj,
    }[exchange]


def _normalize_frame(exchange: str, frame: pd.DataFrame) -> list[ExchangeStockRecord]:
    source = _source_for(exchange)
    columns = {
        "SH": ("证券代码", "证券简称", "上市日期", "所属行业", "板块", None, None),
        "SZ": ("A股代码", "A股简称", "A股上市日期", "所属行业", "板块", "A股总股本", "A股流通股本"),
        "BJ": ("证券代码", "证券简称", "上市日期", "所属行业", None, "总股本", "流通股本"),
    }[exchange]
    code_col, name_col, date_col, industry_col, board_col, total_col, circulating_col = columns
    records: list[ExchangeStockRecord] = []
    for _, row in frame.iterrows():
        code = safe_string(row.get(code_col))
        name = safe_string(row.get(name_col))
        if code is None or name is None or len(code) != 6 or not code.isdigit():
            continue
        records.append(
            ExchangeStockRecord(
                code=code,
                name=name,
                exchange=exchange,
                board=safe_string(row.get(board_col)) if board_col else ("北交所" if exchange == "BJ" else None),
                industry=normalize_exchange_industry(exchange, row.get(industry_col)),
                listing_date=format_listing_date(row.get(date_col)),
                total_shares=safe_float(row.get(total_col)) if total_col else None,
                circulating_shares=safe_float(row.get(circulating_col)) if circulating_col else None,
                source=source.id,
            )
        )
    records_by_code: dict[str, ExchangeStockRecord] = {}
    for record in records:
        records_by_code.setdefault(record.code, record)
    normalized = sorted(records_by_code.values(), key=lambda record: record.code)
    minimum = _MIN_EXCHANGE_RECORDS[exchange]
    if len(normalized) < minimum:
        raise ValueError(f"{exchange} 官方股票名录不足: {len(normalized)} < {minimum}")
    return normalized


def _coerce_record(payload: Any) -> ExchangeStockRecord | None:
    if not isinstance(payload, dict):
        return None
    try:
        record = ExchangeStockRecord(
            code=str(payload["code"]),
            name=str(payload["name"]),
            exchange=str(payload["exchange"]),
            board=safe_string(payload.get("board")),
            industry=normalize_exchange_industry(str(payload["exchange"]), payload.get("industry")),
            listing_date=format_listing_date(payload.get("listing_date")),
            total_shares=safe_float(payload.get("total_shares")),
            circulating_shares=safe_float(payload.get("circulating_shares")),
            source=str(payload["source"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    if record.exchange not in _EXCHANGES or len(record.code) != 6 or not record.code.isdigit():
        return None
    return record


def _load_persisted_slices() -> dict[str, _PersistedExchangeSlice]:
    if not _MASTER_SNAPSHOT_PATH.exists():
        return {}
    try:
        payload = json.loads(_MASTER_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        logger.info("读取交易所统一股票主表失败: %s", error)
        return {}
    raw_exchanges = payload.get("exchanges") if isinstance(payload, dict) else None
    if not isinstance(raw_exchanges, dict):
        return {}
    now = time.time()
    result: dict[str, _PersistedExchangeSlice] = {}
    for exchange in _EXCHANGES:
        raw_slice = raw_exchanges.get(exchange)
        if not isinstance(raw_slice, dict):
            continue
        try:
            fetched_at = float(raw_slice.get("fetched_at", 0))
        except (TypeError, ValueError):
            continue
        if max(0.0, now - fetched_at) > _MASTER_SNAPSHOT_MAX_STALE_SECONDS:
            continue
        raw_records = raw_slice.get("records")
        if not isinstance(raw_records, list):
            continue
        records = [record for item in raw_records if (record := _coerce_record(item)) is not None]
        if len(records) >= _MIN_EXCHANGE_RECORDS[exchange]:
            result[exchange] = _PersistedExchangeSlice(fetched_at=fetched_at, records=records)
    return result


def _save_persisted_slices(slices: dict[str, _PersistedExchangeSlice]) -> None:
    atomic_write_json(
        _MASTER_SNAPSHOT_PATH,
        {
            "version": 1,
            "exchanges": {
                exchange: {
                    "fetched_at": item.fetched_at,
                    "records": [asdict(record) for record in item.records],
                }
                for exchange, item in slices.items()
            },
        },
        indent=0,
    )


async def _fetch_exchange_slice(exchange: str) -> list[ExchangeStockRecord]:
    source = _source_for(exchange)
    frame = await provider_gateway.call(
        source.provider,
        source.operation,
        lambda: call_blocking(_fetcher_for(exchange), semaphore=exchange_semaphore),
        max_attempts=1,
        retry_budget_seconds=8.0,
    )
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{exchange} 官方股票名录返回类型无效")
    return _normalize_frame(exchange, frame)


async def _load_exchange_stock_master(*, force: bool = False) -> ExchangeStockMaster:
    persisted = await call_blocking(_load_persisted_slices, semaphore=misc_semaphore)
    now = time.time()
    fresh_exchanges = {
        exchange
        for exchange, item in persisted.items()
        if not force and max(0.0, now - item.fetched_at) <= _MASTER_CACHE_TTL_SECONDS
    }
    fetch_exchanges = [exchange for exchange in _EXCHANGES if exchange not in fresh_exchanges]
    results = await asyncio.gather(
        *(_fetch_exchange_slice(exchange) for exchange in fetch_exchanges),
        return_exceptions=True,
    )
    slices = dict(persisted)
    failed: dict[str, str] = {}
    stale_exchanges: list[str] = []
    for exchange, result in zip(fetch_exchanges, results, strict=True):
        if isinstance(result, BaseException):
            failed[exchange] = str(result) or type(result).__name__
            if exchange in persisted:
                stale_exchanges.append(exchange)
            continue
        slices[exchange] = _PersistedExchangeSlice(fetched_at=now, records=result)

    records_by_code: dict[str, ExchangeStockRecord] = {}
    for exchange in _EXCHANGES:
        exchange_slice = slices.get(exchange)
        if exchange_slice is None:
            continue
        for record in exchange_slice.records:
            records_by_code.setdefault(record.code, record)
    master = ExchangeStockMaster(
        records=list(records_by_code.values()),
        failed_exchanges=failed,
        stale_exchanges=stale_exchanges,
        fetched_at={exchange: item.fetched_at for exchange, item in slices.items()},
    )
    if fetch_exchanges and slices:
        await call_blocking(_save_persisted_slices, slices, semaphore=misc_semaphore)
    cache.set(
        _MASTER_CACHE_KEY,
        master,
        ttl=_MASTER_RETRY_TTL_SECONDS if failed else _MASTER_CACHE_TTL_SECONDS,
    )
    return master


async def get_exchange_stock_master(*, force: bool = False) -> ExchangeStockMaster:
    if force:
        return await _master_singleflight.do(f"{_MASTER_CACHE_KEY}:refresh", lambda: _load_exchange_stock_master(force=True))
    cached = cache.get(_MASTER_CACHE_KEY)
    if isinstance(cached, ExchangeStockMaster):
        return cached
    return cast(ExchangeStockMaster, await _master_singleflight.do(_MASTER_CACHE_KEY, _load_exchange_stock_master))


async def build_exchange_stock_master() -> None:
    master = await get_exchange_stock_master()
    if not master.records:
        raise RuntimeError("三大交易所统一股票主表为空")
