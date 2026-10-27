import asyncio
import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, cast

from app.configuration import get_settings
from app.configuration.paths import DATA_DIR
from app.core.cache import dated_cache_key_no_day
from app.core.cache import reference_cache as cache
from app.core.concurrency.rate_limiter import call_blocking
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.domain.timezones import market_now
from app.financial_data.market.macro import collector as macro_collector
from app.financial_data.market.macro import normalizer as macro_normalizer
from app.infrastructure.persistence.json_storage import atomic_write_json, durable_unlink
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)
_NBS_MACRO_CONCURRENCY = 8
_AKSHARE_MACRO_CONCURRENCY = 8
_nbs_macro_semaphore = asyncio.Semaphore(_NBS_MACRO_CONCURRENCY)
_akshare_macro_semaphore = asyncio.Semaphore(_AKSHARE_MACRO_CONCURRENCY)
# 宏观抓取专用线程池：akshare 部分接口会无限悬挂（请求无超时），wait_for 超时
# 只能放弃等待、无法终止已运行的线程。悬挂调用若占用共享阻塞线程池，会拖死
# 全应用的 call_blocking（含 SQLite 读写）；专用池的 max_workers 就是悬挂线程
# 的硬上限，最坏情况仅宏观抓取自身降级（排队任务在 wait_for 处依次超时）。
_MACRO_BLOCKING_EXECUTOR = ThreadPoolExecutor(
    max_workers=_NBS_MACRO_CONCURRENCY + _AKSHARE_MACRO_CONCURRENCY,
    thread_name_prefix="macro-blocking",
)


async def _run_macro_blocking(
    func: Callable[[], Any],
    *,
    semaphore: asyncio.Semaphore | None = None,
) -> Any:
    """在宏观专用线程池中执行阻塞抓取，避免悬挂线程拖垮共享线程池。"""
    loop = asyncio.get_running_loop()
    if semaphore is None:
        return await loop.run_in_executor(_MACRO_BLOCKING_EXECUTOR, func)
    async with semaphore:
        return await loop.run_in_executor(_MACRO_BLOCKING_EXECUTOR, func)


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
    "industrial_production": "fetch_china_industrial_production",
    "retail_sales": "fetch_china_retail_sales",
    "fixed_asset_investment": "fetch_china_fixed_asset_investment",
    "real_estate": "fetch_china_real_estate",
    "employment": "fetch_china_employment",
    "lpr": "fetch_china_lpr",
    "shibor": "fetch_china_shibor",
    "trade": "fetch_china_trade",
    "social_financing": "fetch_china_social_financing",
    "us_gdp": "fetch_us_gdp",
    "us_cpi": "fetch_us_cpi",
    "us_labor": "fetch_us_labor",
    "us_pmi": "fetch_us_pmi",
    "us_fed_rate": "fetch_us_fed_rate",
    "us_retail_sales": "fetch_us_retail_sales",
    "us_trade_balance": "fetch_us_trade_balance",
    "us_pce": "fetch_us_pce",
    "us_ppi": "fetch_us_ppi",
    "us_employment_details": "fetch_us_employment_details",
    "us_consumer_confidence": "fetch_us_consumer_confidence",
    "us_credit_spread": "fetch_us_credit_spread",
}
_NBS_FIRST_OPERATIONS = {
    "cpi",
    "ppi",
    "pmi",
    "money_supply",
    "gdp",
    "lpr",
    "trade",
    "shibor",
    "industrial_production",
    "retail_sales",
    "fixed_asset_investment",
    "real_estate",
    "employment",
    "social_financing",
}
_US_OPERATIONS = {operation for operation in _MACRO_METHODS if operation.startswith("us_")}
_FRED_ONLY_OPERATIONS = {"us_pce", "us_employment_details", "us_consumer_confidence", "us_credit_spread"}
# FRED 已下架 ISM PMI 序列：NAPM（制造业）与 NAPMNMI（服务业）均返回
# "The series does not exist."，FRED 站内已无任何 PMI 序列。这些指标不再走 FRED，
# 由东财数据中心直连 + akshare 兜底，避免每次刷新都产生 400 噪音与无效重试。
_FRED_UNSUPPORTED_OPERATIONS = {"us_pmi"}
# 美国宏观中东财数据中心已有直连实现的指标（akshare 依赖金十页面，当前不可用），akshare 兜底；
# 其余 us_* 指标东财侧暂无对应序列，仍走 akshare 单源
_US_EASTMONEY_OPERATIONS = {
    "us_gdp",
    "us_cpi",
    "us_labor",
    "us_pmi",
    "us_fed_rate",
    "us_retail_sales",
    "us_trade_balance",
    "us_ppi",
}
_US_FIELDS = {
    "us_gdp": ["TIME", "VALUE"],
    "us_cpi": ["TIME", "CPI_YOY", "CPI_MOM", "CORE_CPI_YOY", "CORE_CPI_MOM"],
    "us_labor": ["TIME", "UNEMPLOYMENT", "NON_FARM", "INITIAL_JOBLESS"],
    "us_pmi": ["TIME", "MANUFACTURING_PMI", "SERVICES_PMI"],
    "us_fed_rate": ["TIME", "VALUE"],
    "us_retail_sales": ["TIME", "VALUE"],
    "us_trade_balance": ["TIME", "VALUE"],
    "us_pce": ["TIME", "PCE_YOY", "PCE_MOM", "CORE_PCE_YOY", "CORE_PCE_MOM"],
    "us_ppi": ["TIME", "PPI_YOY", "PPI_MOM", "CORE_PPI_YOY", "CORE_PPI_MOM"],
    "us_employment_details": ["TIME", "CIVILIAN_LABOR_PARTICIPATION", "AVG_HOURLY_EARNINGS_MOM"],
    "us_consumer_confidence": ["TIME", "VALUE"],
    "us_credit_spread": ["TIME", "VALUE"],
}
_US_SNAPSHOT_PATH = DATA_DIR / "us_macro_snapshot.json"
# 8：us_pmi 的数据源从 FRED 改为东财，旧快照里的 _SOURCE/_IS_FALLBACK 元数据需重算
_US_SNAPSHOT_SCHEMA_VERSION = 8
_US_SNAPSHOT_MAX_AGE_SECONDS = 6 * 60 * 60
_US_METRIC_FETCH_TIMEOUT_SECONDS = 90
# 单个数据源尝试的上限；前端宏观查询超时为 120s，需为回退链留出多次尝试空间
_MACRO_PROVIDER_TIMEOUT_SECONDS = 25
# NBS 房地产等指标会串行请求多个统计分组，单独放宽以覆盖慢响应。
_NBS_PROVIDER_TIMEOUT_SECONDS = 45
_us_macro_singleflight: AsyncSingleFlight[dict] = AsyncSingleFlight()
_us_refresh_task: asyncio.Task | None = None


_PROVIDER_APIS = {
    "nbs": "https://data.stats.gov.cn/dg/website/publicrelease/web/external/stream/esData",
    "fred": "https://api.stlouisfed.org/fred/series/observations",
    "eastmoney": "https://datacenter-web.eastmoney.com/api/data/v1/get",
    "akshare": "https://akshare.akfamily.xyz/data/macro/macro.html",
}
_PROVIDER_OPERATION_APIS = {
    ("nbs", "lpr"): "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-currency/LprChrtCSV",
    ("nbs", "shibor"): "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-shibor/ShiborHis",
    ("nbs", "social_financing"): (
        "https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
    ),
}
_MONTHLY_OPERATIONS = {
    "cpi",
    "ppi",
    "pmi",
    "money_supply",
    "social_financing",
    "trade",
    "industrial_production",
    "retail_sales",
    "fixed_asset_investment",
    "real_estate",
    "employment",
    *(_US_OPERATIONS - {"us_gdp"}),
}


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
    now = market_now()
    if operation in _MONTHLY_OPERATIONS:
        match = re.search(r"(\d{4})\D?(\d{2})", latest_period)
        if match is None:
            return True
        year, month = int(match.group(1)), int(match.group(2))
        return (now.year * 12 + now.month) - (year * 12 + month) > 2
    if operation in {"gdp", "us_gdp"}:
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
            "_SOURCE_API": _PROVIDER_OPERATION_APIS.get((provider, operation), _PROVIDER_APIS[provider]),
            "_LATEST_PERIOD": latest_period,
            "_IS_FALLBACK": is_fallback,
            "_IS_STALE": is_stale,
            "_FIELD_PERIODS": field_periods,
            "_STALE_FIELDS": stale_fields,
        }
        for row in rows
    ]


def _macro_metric_cache_key(operation: str) -> str:
    # 缓存变体必须与实际数据源一致：FRED 参与的指标随 FRED_API_KEY 变化，
    # 不参与的指标（如 us_pmi）不能因配置了 Key 就换变体，否则会命中旧链路的降级缓存。
    fred_served = (
        operation in _US_OPERATIONS
        and operation not in _FRED_UNSUPPORTED_OPERATIONS
        and bool(get_settings().fred_api_key.strip())
    )
    source_variant = "fred" if fred_served else "default"
    return cast(
        str,
        dated_cache_key_no_day("macro_metric", _MACRO_CACHE_VERSION, operation, source_variant),
    )


async def _load_macro_metric(operation: str) -> object:
    method_name = _MACRO_METHODS.get(operation)
    if method_name is None:
        raise ValueError(f"不支持的宏观指标: {operation}")
    provider_names: tuple[str, ...]
    fred_configured = bool(get_settings().fred_api_key.strip())
    if operation in _FRED_ONLY_OPERATIONS:
        if not fred_configured:
            return []
        provider_names = ("fred",)
    elif operation in _US_EASTMONEY_OPERATIONS:
        provider_names = ("eastmoney", "akshare")
    elif operation in _US_OPERATIONS:
        provider_names = ("akshare",)
    elif operation in _NBS_FIRST_OPERATIONS:
        # 国内宏观数据优先使用官方源聚合 Provider，东财和 akshare 依次兜底。
        provider_names = ("nbs", "eastmoney", "akshare")
    else:
        provider_names = ("eastmoney",)
    if (
        operation in _US_OPERATIONS
        and operation not in _FRED_ONLY_OPERATIONS
        and operation not in _FRED_UNSUPPORTED_OPERATIONS
        and fred_configured
    ):
        provider_names = ("fred", *provider_names)

    last_error: Exception | None = None
    supported_attempts = 0
    providers: dict[str, object] = {}

    def resolve_provider(provider_name: str) -> object:
        if provider_name not in providers:
            providers[provider_name] = get_provider(provider_name)
        return providers[provider_name]

    for index, provider_name in enumerate(provider_names):
        provider = resolve_provider(provider_name)
        fetcher = getattr(provider, method_name, None)
        if not callable(fetcher):
            logger.debug(
                "宏观指标数据源不支持该操作，跳过: operation=%s provider=%s method=%s",
                operation,
                provider_name,
                method_name,
            )
            continue

        is_fallback_attempt = supported_attempts > 0
        supported_attempts += 1
        if provider_name == "nbs":
            semaphore = _nbs_macro_semaphore
        elif provider_name == "akshare":
            semaphore = _akshare_macro_semaphore
        else:
            semaphore = None

        try:
            # 单个数据源尝试限时：akshare 部分接口当前会无限悬挂（请求无超时），
            # 不限时会堵死整条回退链导致指标刷不出来。NBS 使用独立并发额度，
            # 避免全量宏观数据并发加载时在共享信号量中排队并集体超时。
            result = await asyncio.wait_for(
                provider_gateway.call(
                    provider_name,
                    f"macro_{operation}",
                    lambda fetcher=fetcher, semaphore=semaphore: _run_macro_blocking(
                        fetcher,
                        semaphore=semaphore,
                    ),
                    is_fallback_attempt=is_fallback_attempt,
                ),
                timeout=(
                    _NBS_PROVIDER_TIMEOUT_SECONDS
                    if provider_name == "nbs"
                    else _MACRO_PROVIDER_TIMEOUT_SECONDS
                ),
            )
            if not isinstance(result, list) or not result or not all(isinstance(row, dict) for row in result):
                raise ValueError(f"{provider_name} 宏观指标为空或格式无效: {operation}")
            enriched = _with_metric_metadata(
                result,
                operation=operation,
                provider=provider_name,
                is_fallback=is_fallback_attempt,
            )
            # 有实际可用的下游数据源时，当前结果滞后则继续降级；如果后续数据源
            # 根本没有实现该指标，则保留官方源的历史数据而不是返回空结果。
            if provider_name in {"nbs", "akshare"} and enriched[0]["_IS_STALE"]:
                has_supported_fallback = any(
                    callable(getattr(resolve_provider(next_provider_name), method_name, None))
                    for next_provider_name in provider_names[index + 1:]
                )
                if has_supported_fallback:
                    raise ValueError(
                        f"{provider_name} 宏观指标已滞后: "
                        f"{operation} {enriched[0]['_LATEST_PERIOD']}"
                    )
            cache.set(
                _macro_metric_cache_key(operation),
                enriched,
                ttl=2 * 60 * 60 if operation == "us_labor" else (6 * 60 * 60 if operation.startswith("us_") else MACRO_CACHE_TTL_SECONDS),
            )
            return enriched
        except Exception as error:
            last_error = error
            error_detail = str(error).strip() or type(error).__name__
            logger.info(
                "宏观指标数据源失败: operation=%s provider=%s error_type=%s error=%s",
                operation,
                provider_name,
                type(error).__name__,
                error_detail,
            )
    if operation in _FRED_ONLY_OPERATIONS:
        return []
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
        if (
            not isinstance(payload, dict)
            or payload.get("_schema_version") != _US_SNAPSHOT_SCHEMA_VERSION
            or not isinstance(payload.get("indicators"), dict)
        ):
            return None
        payload.pop("_schema_version")
        return payload
    except (OSError, ValueError, TypeError):
        return None


def _save_us_macro_snapshot(payload: dict) -> None:
    atomic_write_json(
        _US_SNAPSHOT_PATH,
        {**payload, "_schema_version": _US_SNAPSHOT_SCHEMA_VERSION},
        indent=0,
    )


def invalidate_us_macro_snapshot() -> bool:
    """使持久化的美国宏观快照失效，让下一次读取使用最新数据源配置刷新。"""
    try:
        removed = durable_unlink(_US_SNAPSHOT_PATH)
    except OSError:
        logger.warning("美国宏观快照失效失败: path=%s", _US_SNAPSHOT_PATH, exc_info=True)
        return False
    if removed:
        logger.info("美国宏观快照已失效: path=%s", _US_SNAPSHOT_PATH)
    return removed


async def _collect_us_macro_data() -> dict:
    operations = tuple(_US_FIELDS)
    # 单指标独立限时：个别源（如当前挂死的 akshare）不允许阻塞整份快照的落盘，
    # 超时/失败只记入 failed_indicators，其余指标正常返回
    values = await asyncio.gather(
        *(
            asyncio.wait_for(
                _fetch_macro_metric(operation, force_refresh=True),
                timeout=_US_METRIC_FETCH_TIMEOUT_SECONDS,
            )
            for operation in operations
        ),
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
