"""个股基础信息服务。"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, replace
from typing import Any, cast

import pandas as pd

from app.configuration import get_settings
from app.configuration.paths import DATA_DIR
from app.core.cache import cache, dated_cache_key
from app.core.cache_policies import BASIC_INFO_FINAL, BASIC_INFO_STATIC
from app.core.concurrency.rate_limiter import (
    call_blocking,
    eastmoney_semaphore,
    exchange_semaphore,
    misc_semaphore,
    tdx_semaphore,
    tencent_semaphore,
)
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import SymbolFormats, normalize_code, safe_float, safe_string
from app.domain.stock import StockConceptInfo
from app.financial_data.stock.profile.industry_normalization import normalize_exchange_industry
from app.financial_data.stock.profile.merger import (
    BasicInfoInputs,
    build_basic_info,
    format_listing_date,
    missing_eastmoney_profile_fields,
)
from app.financial_data.stock.profile.name_map import StockNameMapSnapshot, get_stock_name_map_snapshot
from app.financial_data.stock.profile.schemas import StockBasicInfo
from app.financial_data.stock.profile.sources import (
    EASTMONEY_STOCK_PROFILE,
    TDX_HTTP_FINANCE,
    TDX_HTTP_STOCK_QUOTE,
    TENCENT_STOCK_CONCEPTS,
    TENCENT_STOCK_QUOTE,
    BasicDataSourceSpec,
    exchange_listing_source,
)
from app.financial_data.stock.quotes.sources import get_spot_source
from app.financial_data.stock.quotes.spot_snapshot import get_spot_snapshot, load_spot_snapshot_file
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_basic_info_singleflight: AsyncSingleFlight[StockBasicInfo] = AsyncSingleFlight()
_exchange_listing_singleflight: AsyncSingleFlight[pd.DataFrame] = AsyncSingleFlight()
_EXCHANGE_LISTING_CACHE_TTL_SECONDS = 24 * 60 * 60
_EXCHANGE_LISTING_FAILURE_CACHE_TTL_SECONDS = 5 * 60
_EXCHANGE_LISTING_TIMEOUT_SECONDS = 3.0
_EXCHANGE_LISTING_SNAPSHOT_MAX_STALE_SECONDS = 7 * 24 * 60 * 60
_EXCHANGE_LISTING_SNAPSHOT_PATH = DATA_DIR / "exchange_stock_listing_sz.json"

_EMPTY_STOCK_CONCEPT = StockConceptInfo(
    concepts=[],
    first_concept=None,
    second_concept=None,
)


@dataclass(frozen=True)
class ExchangeBasicData:
    values: dict[str, Any]
    source_id: str


@dataclass(frozen=True)
class _CachedConcepts:
    value: StockConceptInfo | None


@dataclass(frozen=True)
class _ExchangeListingSnapshot:
    frame: pd.DataFrame
    fresh: bool


def _load_exchange_listing_snapshot(exchange: str) -> _ExchangeListingSnapshot | None:
    if exchange != "SZ" or not _EXCHANGE_LISTING_SNAPSHOT_PATH.exists():
        return None
    try:
        payload = json.loads(_EXCHANGE_LISTING_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        records = payload.get("records")
        saved_at = float(payload.get("saved_at", 0))
        if not isinstance(records, list):
            return None
        age_seconds = max(0.0, time.time() - saved_at)
        if age_seconds > _EXCHANGE_LISTING_SNAPSHOT_MAX_STALE_SECONDS:
            return None
        frame = pd.DataFrame(records)
        if frame.empty or "A股代码" not in frame.columns:
            return None
        return _ExchangeListingSnapshot(
            frame=frame,
            fresh=age_seconds <= _EXCHANGE_LISTING_CACHE_TTL_SECONDS,
        )
    except (OSError, TypeError, ValueError) as error:
        logger.info("读取深交所本地名录失败: %s", error)
        return None


def _save_exchange_listing_snapshot(exchange: str, frame: pd.DataFrame) -> None:
    if exchange != "SZ" or frame.empty:
        return
    records = frame.astype(object).where(pd.notna(frame), None).to_dict("records")
    atomic_write_json(
        _EXCHANGE_LISTING_SNAPSHOT_PATH,
        {"saved_at": time.time(), "records": records},
        indent=0,
    )


async def _fetch_provider_blocking(
    provider_name: str,
    operation: str,
    func,
    *args,
    semaphore=None,
    gateway_max_attempts: int | None = None,
    gateway_retry_budget_seconds: float | None = None,
    **kwargs,
):
    return await provider_gateway.call(
        provider_name,
        operation,
        lambda: call_blocking(func, *args, semaphore=semaphore, **kwargs),
        max_attempts=gateway_max_attempts,
        retry_budget_seconds=gateway_retry_budget_seconds,
    )


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


def _get_exchange_provider():
    """Lazily resolve the official exchange provider singleton."""
    return get_provider("exchange")


def _get_tencent_provider():
    """Lazily resolve the Tencent provider singleton."""
    return get_provider("tencent")


def _get_tdx_http_provider():
    """Lazily resolve the TDX HTTP provider singleton."""
    return get_provider("tdx_http")


async def _fetch_optional_tdx_http(
    source: BasicDataSourceSpec,
    method_name: str,
    code: str,
) -> dict[str, Any]:
    if not get_settings().tdx_http_enabled:
        return {}
    fetcher = getattr(_get_tdx_http_provider(), method_name)
    return cast(
        dict[str, Any],
        await _fetch_provider_blocking(
            source.provider,
            source.operation,
            fetcher,
            code,
            semaphore=tdx_semaphore,
        ),
    )


async def _fetch_cached_tencent_concepts(code: str) -> StockConceptInfo | None:
    cache_key = dated_cache_key("stock_concepts", code)
    cached = cache.get(cache_key)
    if isinstance(cached, _CachedConcepts):
        return cached.value
    result = await _fetch_provider_blocking(
        TENCENT_STOCK_CONCEPTS.provider,
        TENCENT_STOCK_CONCEPTS.operation,
        _get_tencent_provider().fetch_stock_concepts,
        code,
        semaphore=tencent_semaphore,
    )
    normalized = result if isinstance(result, StockConceptInfo) else None
    cache.set(cache_key, _CachedConcepts(normalized), ttl=BASIC_INFO_STATIC.ttl_seconds)
    return normalized


async def _fetch_cached_tdx_finance(code: str) -> dict[str, Any]:
    if not get_settings().tdx_http_enabled:
        return {}
    cache_key = dated_cache_key("tdx_http_finance", code)
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cast(dict[str, Any], cached)
    result = await _fetch_optional_tdx_http(
        TDX_HTTP_FINANCE,
        "fetch_finance_info",
        code,
    )
    cache.set(cache_key, result, ttl=BASIC_INFO_STATIC.ttl_seconds)
    return result


async def _fetch_cached_eastmoney_profile(code: str) -> dict[str, Any]:
    cache_key = dated_cache_key("eastmoney_stock_profile", code)
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cast(dict[str, Any], cached)
    result = await _fetch_provider_blocking(
        EASTMONEY_STOCK_PROFILE.provider,
        EASTMONEY_STOCK_PROFILE.operation,
        _get_eastmoney_provider().fetch_stock_basic_info,
        code,
        semaphore=eastmoney_semaphore,
    )
    normalized = result if isinstance(result, dict) else {}
    cache.set(cache_key, normalized, ttl=BASIC_INFO_STATIC.ttl_seconds)
    return cast(dict[str, Any], normalized)


async def _fetch_exchange_basic_row(code: str) -> ExchangeBasicData | None:
    """根据股票代码所属交易所抓取上市信息行。

    Param:
        code: 股票代码
    Return:
        包含 listing_date/industry/shares 的字典，找不到时返回 None
    """
    exchange = normalize_code(code).exchange
    source = exchange_listing_source(exchange)
    row_scoped = exchange in {"SH", "BJ"}
    cache_key = dated_cache_key("exchange_stock_listing", exchange, code if row_scoped else "all")
    cached = cache.get(cache_key)
    if isinstance(cached, pd.DataFrame):
        df = cached
    else:
        disk_snapshot = (
            await call_blocking(_load_exchange_listing_snapshot, exchange, semaphore=misc_semaphore)
            if not row_scoped
            else None
        )
        if disk_snapshot is not None and disk_snapshot.fresh:
            cache.set(cache_key, disk_snapshot.frame, ttl=_EXCHANGE_LISTING_CACHE_TTL_SECONDS)
            df = disk_snapshot.frame
        else:

            async def load_listing() -> pd.DataFrame:
                fetch_args: tuple[str, ...] = ()
                if exchange == "SH":
                    fetcher = _get_exchange_provider().fetch_stock_names_sh
                    fetch_args = (code,)
                elif exchange == "SZ":
                    fetcher = _get_exchange_provider().fetch_stock_names_sz
                elif exchange == "BJ":
                    fetcher = _get_exchange_provider().fetch_stock_names_bj
                    fetch_args = (code,)
                else:
                    return pd.DataFrame()
                try:
                    frame = await _fetch_provider_blocking(
                        source.provider,
                        source.operation,
                        fetcher,
                        *fetch_args,
                        semaphore=exchange_semaphore,
                        gateway_max_attempts=1,
                        gateway_retry_budget_seconds=_EXCHANGE_LISTING_TIMEOUT_SECONDS,
                    )
                except Exception:
                    if disk_snapshot is not None:
                        logger.info("深交所远程名录不可用，使用本地快照")
                        cache.set(
                            cache_key,
                            disk_snapshot.frame,
                            ttl=_EXCHANGE_LISTING_FAILURE_CACHE_TTL_SECONDS,
                        )
                        return disk_snapshot.frame
                    cache.set(
                        cache_key,
                        pd.DataFrame(),
                        ttl=_EXCHANGE_LISTING_FAILURE_CACHE_TTL_SECONDS,
                    )
                    raise
                cache.set(cache_key, frame, ttl=_EXCHANGE_LISTING_CACHE_TTL_SECONDS)
                await call_blocking(
                    _save_exchange_listing_snapshot,
                    exchange,
                    frame,
                    semaphore=misc_semaphore,
                )
                return frame

            df = await _exchange_listing_singleflight.do(cache_key, load_listing)

    code_column = {"SH": "证券代码", "SZ": "A股代码", "BJ": "证券代码"}.get(exchange)
    if df.empty or code_column is None or code_column not in df.columns:
        return None

    if exchange == "SH":
        row = df[df[code_column] == code]
        if row.empty:
            return None
        r = row.iloc[0]
        return ExchangeBasicData(
            values={
                "name": safe_string(r.get("证券简称")),
                "listing_date": format_listing_date(r.get("上市日期")),
                "industry": normalize_exchange_industry(exchange, r.get("所属行业")),
                "total_shares": None,
                "circulating_shares": None,
            },
            source_id=source.id,
        )
    if exchange == "SZ":
        row = df[df[code_column] == code]
        if row.empty:
            return None
        r = row.iloc[0]
        return ExchangeBasicData(
            values={
                "name": safe_string(r.get("A股简称")),
                "listing_date": format_listing_date(r.get("A股上市日期")),
                "industry": normalize_exchange_industry(exchange, r.get("所属行业")),
                "total_shares": safe_float(str(r.get("A股总股本", "")).replace(",", "")),
                "circulating_shares": safe_float(str(r.get("A股流通股本", "")).replace(",", "")),
            },
            source_id=source.id,
        )
    if exchange == "BJ":
        row = df[df[code_column] == code]
        if row.empty:
            return None
        r = row.iloc[0]
        return ExchangeBasicData(
            values={
                "name": safe_string(r.get("证券简称")),
                "listing_date": format_listing_date(r.get("上市日期")),
                "industry": normalize_exchange_industry(exchange, r.get("所属行业")),
                "total_shares": safe_float(r.get("总股本")),
                "circulating_shares": safe_float(r.get("流通股本")),
            },
            source_id=source.id,
        )
    return None


async def _load_basic_info_spot_df() -> pd.DataFrame | None:
    """加载市场快照 DataFrame，按缓存/本地/远程顺序回退。

    Param:
        无
    Return:
        市场快照 DataFrame，全部失败时返回 None
    """
    spot_df = cache.get("stock_spot_all")
    if spot_df is not None:
        return spot_df

    spot_df = load_spot_snapshot_file()
    if spot_df is not None:
        return spot_df

    try:
        return await asyncio.wait_for(get_spot_snapshot(), timeout=2.0)
    except Exception as e:
        logger.info("实时快照获取失败: %s", e)
        return None


def _find_spot_row(spot_df: pd.DataFrame | None, code: str):
    """在快照 DataFrame 中查找指定代码对应的行。

    Param:
        spot_df: 全市场快照 DataFrame
        code: 股票代码
    Return:
        匹配的 Series，未找到时返回 None
    """
    if spot_df is None:
        return None
    matched = spot_df[spot_df["代码"] == code]
    if matched.empty:
        return None
    return matched.iloc[0]


async def _load_basic_info(sym: SymbolFormats, cache_key: str) -> StockBasicInfo:
    """聚合多数据源并缓存股票基本信息。

    Param:
        sym: 归一化后的股票代码
        cache_key: 基础信息缓存键
    Return:
        StockBasicInfo 模型对象，包含估值、股本、行业等字段
    """
    (
        spot_result,
        exchange_result,
        name_map_result,
        concept_result,
        quote_result,
        tdx_quote_result,
        tdx_finance_result,
    ) = await asyncio.gather(
        _load_basic_info_spot_df(),
        asyncio.wait_for(_fetch_exchange_basic_row(sym.raw), timeout=_EXCHANGE_LISTING_TIMEOUT_SECONDS),
        get_stock_name_map_snapshot(),
        _fetch_cached_tencent_concepts(sym.raw),
        _fetch_provider_blocking(
            TENCENT_STOCK_QUOTE.provider,
            TENCENT_STOCK_QUOTE.operation,
            _get_tencent_provider().fetch_stock_quote,
            sym.raw,
            semaphore=tencent_semaphore,
        ),
        _fetch_optional_tdx_http(
            TDX_HTTP_STOCK_QUOTE,
            "fetch_stock_quote",
            sym.raw,
        ),
        _fetch_cached_tdx_finance(sym.raw),
        return_exceptions=True,
    )

    if isinstance(exchange_result, Exception):
        logger.info("交易所基础信息不可用: code=%s, error=%s", sym.raw, exchange_result)
    if isinstance(concept_result, Exception):
        logger.info("腾讯行业概念不可用: code=%s, error=%s", sym.raw, concept_result)
    if isinstance(quote_result, Exception):
        logger.info("腾讯实时行情不可用: code=%s, error=%s", sym.raw, quote_result)
    if isinstance(tdx_quote_result, Exception):
        logger.info("TDX HTTP 实时行情不可用: code=%s, error=%s", sym.raw, tdx_quote_result)
    if isinstance(tdx_finance_result, Exception):
        logger.info("TDX HTTP 财务信息不可用: code=%s, error=%s", sym.raw, tdx_finance_result)

    spot_df = spot_result if isinstance(spot_result, pd.DataFrame) else None
    exchange_data = exchange_result if isinstance(exchange_result, ExchangeBasicData) else None
    name_map_snapshot = name_map_result if isinstance(name_map_result, StockNameMapSnapshot) else StockNameMapSnapshot.empty()
    concepts_available = isinstance(concept_result, StockConceptInfo)
    stock_concepts = concept_result if concepts_available else _EMPTY_STOCK_CONCEPT
    tencent_quote = quote_result if isinstance(quote_result, dict) else {}
    tdx_http_quote = tdx_quote_result if isinstance(tdx_quote_result, dict) else {}
    tdx_http_finance = tdx_finance_result if isinstance(tdx_finance_result, dict) else {}
    primary_inputs = BasicInfoInputs(
        eastmoney_profile={},
        exchange_profile=exchange_data.values if exchange_data else {},
        exchange_source_id=(exchange_data.source_id if exchange_data else exchange_listing_source(sym.exchange).id),
        spot_row=_find_spot_row(spot_df, sym.raw),
        spot_source_id=get_spot_source(spot_df),
        name_map=name_map_snapshot.mapping,
        name_map_source_id=name_map_snapshot.source_for(sym.raw),
        stock_concepts=stock_concepts,
        concepts_available=concepts_available,
        tencent_quote=tencent_quote,
        tdx_http_quote=tdx_http_quote,
        tdx_http_finance=tdx_http_finance,
    )
    result = build_basic_info(sym, primary_inputs)
    missing_fields = missing_eastmoney_profile_fields(result)
    if missing_fields:
        try:
            profile_result = await _fetch_cached_eastmoney_profile(sym.raw)
        except Exception as error:
            logger.info(
                "东方财富个股资料备用源不可用: code=%s, missing=%s, error=%s",
                sym.raw,
                ",".join(missing_fields),
                error,
            )
        else:
            if isinstance(profile_result, dict):
                result = build_basic_info(
                    sym,
                    replace(primary_inputs, eastmoney_profile=profile_result),
                )

    cache.set(cache_key, result, ttl=BASIC_INFO_FINAL.ttl_seconds)
    return result


async def get_basic_info(code: str) -> StockBasicInfo:
    """获取股票基本信息，融合东财、交易所、腾讯等多数据源。"""
    sym = normalize_code(code)
    cache_key = dated_cache_key("stock_basic_info", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    return await _basic_info_singleflight.do(
        cache_key,
        lambda: _load_basic_info(sym, cache_key),
    )
