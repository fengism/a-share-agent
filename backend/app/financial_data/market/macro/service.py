import asyncio
import logging
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from app.configuration.paths import DATA_DIR
from app.core.cache import cache, dated_cache_key_no_day
from app.core.concurrency.rate_limiter import call_blocking
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.financial_data.market.macro import collector as macro_collector
from app.financial_data.market.macro import normalizer as macro_normalizer
from app.infrastructure.persistence.json_storage import atomic_write_json
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)
_akshare_macro_semaphore = asyncio.Semaphore(8)
_macro_singleflight: AsyncSingleFlight[dict] = AsyncSingleFlight()
_macro_metric_singleflight: AsyncSingleFlight[object] = AsyncSingleFlight()
_eastmoney_provider = None
MACRO_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_MACRO_DATA_FLIGHT_KEY = "macro_data"
_MACRO_ALL_DATA_FLIGHT_KEY = "macro_all_data"
_MACRO_CACHE_VERSION = "v2"
_MACRO_METHODS = {
    "cpi": "fetch_china_cpi",
    "ppi": "fetch_china_ppi",
    "pmi": "fetch_china_pmi",
    "money_supply": "fetch_china_economy_currency_supply",
    "gdp": "fetch_china_gdp",
    "lpr": "fetch_china_lpr",
    "shibor": "fetch_china_shibor",
    "trade": "fetch_china_trade",
    "social_financing": "fetch_china_social_financing",
    "us_gdp": "fetch_us_gdp",
    "us_cpi": "fetch_us_cpi",
    "us_core_pce": "fetch_us_core_pce",
    "us_labor": "fetch_us_labor",
    "us_pmi": "fetch_us_pmi",
    "us_fed_rate": "fetch_us_fed_rate",
    "us_retail_sales": "fetch_us_retail_sales",
    "us_trade_balance": "fetch_us_trade_balance",
}
_NBS_FIRST_OPERATIONS = {"cpi", "ppi", "pmi", "gdp"}
_AKSHARE_ONLY_OPERATIONS = {operation for operation in _MACRO_METHODS if operation.startswith("us_")}
_AKSHARE_CHINA_OPERATIONS = {"cpi", "ppi", "pmi", "gdp", "money_supply", "lpr", "shibor", "trade", "social_financing"}
_US_FIELDS = {
    "us_gdp": ["TIME", "VALUE"],
    "us_cpi": ["TIME", "CPI_YOY", "CPI_MOM", "CORE_CPI_MOM"],
    "us_core_pce": ["TIME", "VALUE"],
    "us_labor": ["TIME", "UNEMPLOYMENT", "NON_FARM", "INITIAL_JOBLESS"],
    "us_pmi": ["TIME", "MANUFACTURING_PMI", "SERVICES_PMI"],
    "us_fed_rate": ["TIME", "VALUE"],
    "us_retail_sales": ["TIME", "VALUE"],
    "us_trade_balance": ["TIME", "VALUE"],
}
_US_SNAPSHOT_PATH = DATA_DIR / "us_macro_snapshot.json"
_US_SNAPSHOT_MAX_AGE_SECONDS = 6 * 60 * 60
_us_macro_singleflight: AsyncSingleFlight[dict] = AsyncSingleFlight()
_us_refresh_task: asyncio.Task | None = None


_PROVIDER_APIS = {
    "nbs": "https://data.stats.gov.cn/dg/website/publicrelease/web/external/stream/esData",
    "eastmoney": "https://datacenter-web.eastmoney.com/api/data/v1/get",
    "akshare": "https://akshare.akfamily.xyz/data/macro/macro.html",
}
_MONTHLY_OPERATIONS = {"cpi", "ppi", "pmi", "money_supply", "social_financing", "trade", *_AKSHARE_ONLY_OPERATIONS}


def _latest_period(operation: str, rows: list[dict]) -> str | None:
    if not rows:
        return None
    row = rows[0]
    for key in ("TIME", "REPORT_DATE", "TRADE_DATE"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return None


def _is_stale_metric(operation: str, latest_period: str | None) -> bool:
    if latest_period is None:
        return True
    now = datetime.now()
    if operation in _MONTHLY_OPERATIONS:
        match = re.search(r"(\d{4})\D?(\d{2})", latest_period)
        if match is None:
            return True
        year, month = int(match.group(1)), int(match.group(2))
        return (now.year * 12 + now.month) - (year * 12 + month) > 2
    if operation == "gdp":
        match = re.search(r"(\d{4})Q([1-4])", latest_period)
        if match is None:
            return True
        year, quarter = int(match.group(1)), int(match.group(2))
        current_quarter = (now.month - 1) // 3 + 1
        return (now.year * 4 + current_quarter) - (year * 4 + quarter) > 1
    return False


def _with_metric_metadata(
    rows: list[dict],
    *,
    operation: str,
    provider: str,
    is_fallback: bool,
) -> list[dict]:
    latest_period = _latest_period(operation, rows)
    is_stale = _is_stale_metric(operation, latest_period)
    raw_field_periods = rows[0].get("_FIELD_PERIODS")
    if isinstance(raw_field_periods, dict):
        field_periods = {str(field): str(period) for field, period in raw_field_periods.items()}
    else:
        field_periods = {
            str(field): str(latest_period)
            for field, value in rows[0].items()
            if field != "TIME" and not str(field).startswith("_") and value is not None and latest_period is not None
        }
    stale_fields = [
        field for field, period in field_periods.items()
        if _is_stale_metric(operation, period)
    ]
    return [
        {
            **row,
            "_SOURCE": provider,
            "_SOURCE_API": _PROVIDER_APIS[provider],
            "_LATEST_PERIOD": latest_period,
            "_IS_FALLBACK": is_fallback,
            "_IS_STALE": is_stale,
            "_FIELD_PERIODS": field_periods,
            "_STALE_FIELDS": stale_fields,
        }
        for row in rows
    ]


def _macro_metric_cache_key(operation: str) -> str:
    return cast(str, dated_cache_key_no_day("macro_metric", _MACRO_CACHE_VERSION, operation))


async def _load_macro_metric(operation: str) -> object:
    method_name = _MACRO_METHODS.get(operation)
    if method_name is None:
        raise ValueError(f"不支持的宏观指标: {operation}")
    provider_names: tuple[str, ...]
    if operation in _AKSHARE_ONLY_OPERATIONS:
        provider_names = ("akshare",)
    elif operation in _NBS_FIRST_OPERATIONS:
        provider_names = ("akshare", "nbs", "eastmoney")
    elif operation == "money_supply":
        provider_names = ("akshare", "eastmoney", "nbs")
    elif operation in _AKSHARE_CHINA_OPERATIONS:
        provider_names = ("akshare", "eastmoney")
    else:
        provider_names = ("eastmoney",)

    last_error: Exception | None = None
    for index, provider_name in enumerate(provider_names):
        provider = get_provider(provider_name)
        try:
            result = await provider_gateway.call(
                provider_name,
                f"macro_{operation}",
                lambda provider=provider: call_blocking(
                    getattr(provider, method_name),
                    semaphore=_akshare_macro_semaphore if provider_name == "akshare" else None,
                ),
                is_fallback_attempt=index > 0,
            )
            if not isinstance(result, list) or not result or not all(isinstance(row, dict) for row in result):
                raise ValueError(f"{provider_name} 宏观指标为空或格式无效: {operation}")
            enriched = _with_metric_metadata(
                result,
                operation=operation,
                provider=provider_name,
                is_fallback=index > 0,
            )
            if provider_name in {"nbs", "akshare"} and len(provider_names) > 1 and enriched[0]["_IS_STALE"]:
                raise ValueError(f"{provider_name} 宏观指标已滞后: {operation} {enriched[0]['_LATEST_PERIOD']}")
            cache.set(
                _macro_metric_cache_key(operation),
                enriched,
                ttl=2 * 60 * 60 if operation == "us_labor" else (6 * 60 * 60 if operation.startswith("us_") else MACRO_CACHE_TTL_SECONDS),
            )
            return enriched
        except Exception as error:
            last_error = error
            logger.info(
                "宏观指标数据源失败: operation=%s provider=%s error=%s",
                operation,
                provider_name,
                error,
            )
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"宏观指标数据源为空: {operation}")


async def _fetch_macro_metric(
    operation: str,
    _legacy_fetcher: Callable[..., Any] | None = None,
    *,
    force_refresh: bool = False,
) -> object:
    cache_key = _macro_metric_cache_key(operation)
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    return await _macro_metric_singleflight.do(
        cache_key,
        lambda: _load_macro_metric(operation),
    )


def _get_eastmoney_provider():
    global _eastmoney_provider
    if _eastmoney_provider is None:
        _eastmoney_provider = get_provider("eastmoney")
    return _eastmoney_provider


def _extract_latest(data: list[dict], keys: list[str]) -> dict | None:
    return cast(dict | None, macro_normalizer.extract_latest(data, keys))


def _extract_recent(data: list[dict], keys: list[str], n: int = 3) -> list[dict]:
    return cast(list[dict], macro_normalizer.extract_recent(data, keys, n))


async def get_macro_data() -> dict:
    """获取 CPI、PPI、PMI 和货币供应量摘要。"""
    return cast(dict, await _macro_singleflight.do(
        _MACRO_DATA_FLIGHT_KEY,
        _load_macro_data,
    ))


async def _load_macro_data() -> dict:
    collected = await macro_collector.collect_basic(
        _get_eastmoney_provider(),
        _fetch_macro_metric,
    )
    result = macro_normalizer.normalize_basic(
        collected,
        logger,
        _extract_latest,
        _extract_recent,
    )
    return cast(dict, result)


async def get_macro_all_data(force_refresh: bool = False) -> dict:
    """获取物价、景气、货币、利率、增速和外贸全量宏观数据。"""
    return cast(dict, await _macro_singleflight.do(
        (_MACRO_ALL_DATA_FLIGHT_KEY, force_refresh),
        lambda: _load_macro_all_data(force_refresh=force_refresh),
    ))


async def _load_macro_all_data(*, force_refresh: bool = False) -> dict:
    fetch_metric: macro_collector.MetricFetcher = _fetch_macro_metric
    if force_refresh:
        async def force_fetch_metric(operation: str, fetcher: Callable) -> object:
            return await _fetch_macro_metric(operation, fetcher, force_refresh=True)

        fetch_metric = force_fetch_metric

    collected = await macro_collector.collect_full(
        _get_eastmoney_provider(),
        fetch_metric,
    )
    result = macro_normalizer.normalize_full(
        collected,
        logger,
        _extract_latest,
        _extract_recent,
    )
    return cast(dict, result)


def _load_us_macro_snapshot() -> dict | None:
    if not _US_SNAPSHOT_PATH.exists():
        return None
    try:
        import json
        payload = json.loads(_US_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("indicators"), dict):
            return None
        return payload
    except (OSError, ValueError, TypeError):
        return None


def _save_us_macro_snapshot(payload: dict) -> None:
    atomic_write_json(_US_SNAPSHOT_PATH, payload, indent=0)


async def _collect_us_macro_data() -> dict:
    operations = tuple(_US_FIELDS)
    values = await asyncio.gather(
        *(_fetch_macro_metric(operation, force_refresh=True) for operation in operations),
        return_exceptions=True,
    )
    failed = {
        operation.removeprefix("us_"): str(value) or type(value).__name__
        for operation, value in zip(operations, values, strict=True)
        if isinstance(value, Exception)
    }
    indicators = {
        operation.removeprefix("us_"): macro_normalizer.normalize_generic(
            value, _US_FIELDS[operation], 24, operation, logger,
        )
        for operation, value in zip(operations, values, strict=True)
    }
    payload = {
        "indicators": indicators,
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "refreshing": False,
        "failed_indicators": failed,
    }
    await call_blocking(_save_us_macro_snapshot, payload)
    return payload


async def _refresh_us_macro_data() -> dict:
    return cast(dict, await _us_macro_singleflight.do("us_macro_snapshot", _collect_us_macro_data))


def _start_us_macro_refresh() -> None:
    global _us_refresh_task
    if _us_refresh_task is not None and not _us_refresh_task.done():
        return
    _us_refresh_task = asyncio.create_task(_refresh_us_macro_data(), name="us_macro_refresh")

    def finish(task: asyncio.Task) -> None:
        global _us_refresh_task
        try:
            task.result()
        except Exception:
            logger.warning("美国宏观后台刷新失败", exc_info=True)
        finally:
            _us_refresh_task = None

    _us_refresh_task.add_done_callback(finish)


async def prewarm_us_macro_data() -> None:
    snapshot = await call_blocking(_load_us_macro_snapshot)
    if snapshot is None:
        _start_us_macro_refresh()
        return
    try:
        updated_at = datetime.fromisoformat(str(snapshot.get("updated_at"))).timestamp()
    except (TypeError, ValueError):
        updated_at = 0
    if time.time() - updated_at > _US_SNAPSHOT_MAX_AGE_SECONDS:
        _start_us_macro_refresh()


async def get_us_macro_data(force_refresh: bool = False) -> dict:
    if force_refresh:
        return await _refresh_us_macro_data()
    snapshot = await call_blocking(_load_us_macro_snapshot)
    if snapshot is None:
        return await _refresh_us_macro_data()
    try:
        updated_at = datetime.fromisoformat(str(snapshot.get("updated_at"))).timestamp()
    except (TypeError, ValueError):
        updated_at = 0
    stale = time.time() - updated_at > _US_SNAPSHOT_MAX_AGE_SECONDS
    if stale:
        _start_us_macro_refresh()
    return {**snapshot, "refreshing": stale}
