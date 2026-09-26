"""个股财务数据服务。"""

import asyncio
import logging
from collections.abc import Mapping
from datetime import date

import pandas as pd

from app.constants.financial_labels import FINANCIAL_METRIC_ALIASES, FINANCIAL_METRIC_LABELS
from app.core.cache import dated_cache_key_no_day
from app.core.cache import reference_cache as cache
from app.core.concurrency.rate_limiter import akshare_semaphore, sina_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.core.market import normalize_code, safe_float
from app.financial_data.stock.fundamentals.schemas import FinancialMetrics, RevenueBreakdown
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_FINANCIAL_CACHE_TTL_SECONDS = 86400
_FINANCIAL_CACHE_SCHEMA = "v4"
_FINANCIAL_FETCH_PERIODS = 8
_FINANCIAL_PRESENTATION_PERIODS = 4
_FINANCIAL_INDICATORS = frozenset({"balance", "profit", "cashflow"})
_financial_statement_singleflight: AsyncSingleFlight[list[dict]] = AsyncSingleFlight()
_financial_metrics_singleflight: AsyncSingleFlight[FinancialMetrics] = AsyncSingleFlight()
_revenue_breakdown_singleflight: AsyncSingleFlight[RevenueBreakdown] = AsyncSingleFlight()


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_sina_provider():
    """Lazily resolve the Sina provider singleton."""
    return get_provider("sina")


async def _load_financial_statement(sym, indicator: str, cache_key: str) -> list[dict]:
    source = "sina"
    try:
        df = await provider_gateway.call_blocking(
            "sina",
            f"stock_financials_{indicator}",
            _get_sina_provider().fetch_stock_financials,
            sym.raw,
            indicator,
            num=_FINANCIAL_FETCH_PERIODS,
            semaphore=sina_semaphore,
        )
    except Exception as sina_error:
        logger.warning(
            "新浪财报不可用，回退 AkShare: code=%s indicator=%s error_type=%s",
            sym.raw,
            indicator,
            type(sina_error).__name__,
        )
        # 显式赋值而不是靠 "sina_error" in locals() 推断：PEP 3110 会在 except 块
        # 结束时删掉异常名，那个判断恒为 False，日志会一直把兜底结果标成 source=sina。
        source = "akshare"
        try:
            df = await provider_gateway.call_blocking(
                "akshare",
                f"stock_financials_{indicator}",
                _get_akshare_provider().fetch_stock_financials,
                symbol=sym.prefixed_upper,
                indicator=indicator,
                semaphore=akshare_semaphore,
                is_fallback_attempt=True,
            )
        except Exception as error:
            raise UpstreamUnavailableError(f"{sym.raw} 财务报表上游暂时不可用") from error
    result = _normalize_financial_statement_records(
        df.fillna("N/A").to_dict(orient="records")
    )
    logger.info(
        "financial statement loaded code=%s indicator=%s source=%s rows=%s latest_report_date=%s",
        sym.raw,
        indicator,
        source,
        len(result),
        next((row.get("REPORT_DATE") or row.get("REPORT_DATE_NAME") for row in result), None),
    )
    cache.set(cache_key, result, ttl=_FINANCIAL_CACHE_TTL_SECONDS)
    return result


async def get_revenue_breakdown(code: str) -> RevenueBreakdown:
    """获取新浪最新披露的分产品、业务和地区营收与毛利构成。"""
    sym = normalize_code(code)
    cache_key = dated_cache_key_no_day("revenue_breakdown", "v1", sym.prefixed_upper)
    cached = cache.get(cache_key)
    if cached is not None:
        return RevenueBreakdown.model_validate(cached)

    async def load_and_cache() -> RevenueBreakdown:
        cached_inside_flight = cache.get(cache_key)
        if cached_inside_flight is not None:
            return RevenueBreakdown.model_validate(cached_inside_flight)
        try:
            payload = await provider_gateway.call_blocking(
                "sina",
                "stock_revenue_breakdown",
                _get_sina_provider().fetch_revenue_breakdown,
                sym.raw,
                semaphore=sina_semaphore,
            )
            result = RevenueBreakdown.model_validate(payload)
        except Exception as error:
            raise UpstreamUnavailableError(f"{sym.raw} 营收与毛利构成上游暂时不可用") from error
        cache.set(cache_key, result, ttl=_FINANCIAL_CACHE_TTL_SECONDS)
        return result

    return await _revenue_breakdown_singleflight.do(cache_key, load_and_cache)


async def get_financial(code: str, indicator: str = "balance") -> list[dict]:
    """获取股票最近 4 期财报数据，并复用同类型报表加载结果。

    Param:
        code: 股票代码
        indicator: 报表类型，balance/profit/cashflow 之一
    Return:
        财报字典列表，每项为一期数据
    """
    if indicator not in _FINANCIAL_INDICATORS:
        raise ValueError(f"不支持的财报类型: {indicator}")
    sym = normalize_code(code)
    cache_key = dated_cache_key_no_day("financial", _FINANCIAL_CACHE_SCHEMA, sym.prefixed_upper, indicator)
    cached = cache.get(cache_key)
    if cached is not None:
        try:
            return _normalize_financial_statement_records(cached)
        except (TypeError, ValueError) as error:
            logger.warning(
                "财务报表缓存格式异常，重新回源: code=%s indicator=%s error_type=%s",
                sym.raw,
                indicator,
                type(error).__name__,
            )
    return await _financial_statement_singleflight.do(
        cache_key,
        lambda: _load_financial_statement(sym, indicator, cache_key),
    )


_FINANCIAL_REPORT_DATE_COLUMNS = ["REPORT_DATE", "REPORT_DATE_NAME", "REPORT_DATE_NOTICE", "REPORT_DATE_ORG", "日期", "报告日期", "报告期"]
_FINANCIAL_DISCLOSURE_DATE_COLUMNS = ["UPDATE_DATE", "更新日期", "NOTICE_DATE", "公告日期"]


def _find_report_date_column(df: pd.DataFrame) -> str | None:
    """在财报 DataFrame 中查找报告期列名。

    Param:
        df: 财报 DataFrame
    Return:
        报告期列名，未找到时返回 None
    """
    for column in _FINANCIAL_REPORT_DATE_COLUMNS:
        if column in df.columns:
            return column
    return None


def _normalize_report_date(value) -> str | None:
    """规范化报告期字段为字符串。

    Param:
        value: 原始报告期值
    Return:
        去空格后的字符串，空值返回 None
    """
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _parse_financial_date(value: object) -> date | None:
    text = _normalize_report_date(value)
    if text is None:
        return None
    try:
        parsed = pd.Timestamp(text)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _record_period(record: Mapping[str, object]) -> tuple[str | None, date | None]:
    for column in _FINANCIAL_REPORT_DATE_COLUMNS:
        raw_period = _normalize_report_date(record.get(column))
        if raw_period is not None:
            parsed_period = _parse_financial_date(raw_period)
            identity = parsed_period.isoformat() if parsed_period is not None else raw_period
            return identity, parsed_period
    return None, None


def _record_disclosure_date(record: Mapping[str, object]) -> date | None:
    dates = [
        parsed
        for column in _FINANCIAL_DISCLOSURE_DATE_COLUMNS
        if (parsed := _parse_financial_date(record.get(column))) is not None
    ]
    return max(dates) if dates else None


def _normalize_financial_statement_records(records: object) -> list[dict]:
    """按报告期倒序去重，并返回最近四个报告期。"""
    if not isinstance(records, list):
        raise TypeError("财务报表记录必须为列表")

    decorated = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise TypeError("财务报表记录项必须为映射")
        copied = dict(record)
        period_identity, period_date = _record_period(copied)
        disclosure_date = _record_disclosure_date(copied)
        decorated.append((copied, index, period_identity, period_date, disclosure_date))

    decorated.sort(
        key=lambda item: (
            0 if item[3] is not None else 1,
            -item[3].toordinal() if item[3] is not None else 0,
            -item[4].toordinal() if item[4] is not None else 0,
            item[1],
        )
    )

    result: list[dict] = []
    seen_periods: set[str] = set()
    for record, _, period_identity, _, _ in decorated:
        if period_identity is not None:
            if period_identity in seen_periods:
                continue
            seen_periods.add(period_identity)
        result.append(record)
        if len(result) == _FINANCIAL_PRESENTATION_PERIODS:
            break
    return result


def _financial_rows_by_date(df: pd.DataFrame) -> dict[str, pd.Series]:
    if df.empty:
        return {}
    if _find_report_date_column(df) is None:
        return {}
    rows: dict[str, pd.Series] = {}
    disclosure_dates: dict[str, date | None] = {}
    for _, row in df.iterrows():
        record = row.to_dict()
        report_date, _ = _record_period(record)
        if report_date is None:
            continue
        disclosure_date = _record_disclosure_date(record)
        existing_disclosure_date = disclosure_dates.get(report_date)
        if report_date not in rows or (
            disclosure_date is not None
            and (existing_disclosure_date is None or disclosure_date > existing_disclosure_date)
        ):
            rows[report_date] = row
            disclosure_dates[report_date] = disclosure_date
    return rows


def _get_latest_financial_row(df: pd.DataFrame) -> tuple[pd.Series | None, str | None]:
    """提取财报 DataFrame 的最新行和对应报告期。"""
    rows = _financial_rows_by_date(df)
    if not rows:
        return None, None
    report_date = max(rows)
    return rows[report_date], report_date


def _pick_financial_value(row: pd.Series | None, aliases: list[str]) -> float | None:
    """按别名列表从财报行中提取首个有效数值。

    Param:
        row: 财报数据行
        aliases: 待匹配的列名列表
    Return:
        首个非空数值，全部缺失时返回 None
    """
    if row is None:
        return None
    for alias in aliases:
        if alias in row.index:
            value = safe_float(row.get(alias))
            if value is not None:
                return value
    return None


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    """安全除法，避免除零或空值。

    Param:
        numerator: 分子
        denominator: 分母
    Return:
        保留 4 位小数的商，无效时返回 None
    """
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator, 4)


def _build_financial_metrics(balance_df: pd.DataFrame, profit_df: pd.DataFrame, cashflow_df: pd.DataFrame) -> tuple[str | None, dict[str, float | None]]:
    """汇总资产、利润、现金流三表关键指标并计算衍生指标。

    Param:
        balance_df: 资产负债表 DataFrame
        profit_df: 利润表 DataFrame
        cashflow_df: 现金流量表 DataFrame
    Return:
        (最新报告期, 本地化指标字典) 元组
    """
    balance_rows = _financial_rows_by_date(balance_df)
    profit_rows = _financial_rows_by_date(profit_df)
    cashflow_rows = _financial_rows_by_date(cashflow_df)
    common_dates = set(balance_rows) & set(profit_rows) & set(cashflow_rows)
    latest_report_date = max(common_dates) if common_dates else None
    balance_row = balance_rows.get(latest_report_date) if latest_report_date else None
    profit_row = profit_rows.get(latest_report_date) if latest_report_date else None
    cashflow_row = cashflow_rows.get(latest_report_date) if latest_report_date else None

    metrics = {
        name: _pick_financial_value(balance_row, aliases)
        for name, aliases in FINANCIAL_METRIC_ALIASES.items()
        if name in {"total_assets", "total_liabilities", "shareholders_equity", "cash", "accounts_receivable", "inventory"}
    }
    metrics.update({
        name: _pick_financial_value(profit_row, aliases)
        for name, aliases in FINANCIAL_METRIC_ALIASES.items()
        if name in {"revenue", "revenue_yoy", "operating_profit", "net_profit", "net_profit_yoy", "non_net_profit", "non_net_profit_yoy"}
    })
    metrics.update({
        name: _pick_financial_value(cashflow_row, aliases)
        for name, aliases in FINANCIAL_METRIC_ALIASES.items()
        if name in {"operating_cashflow", "investing_cashflow", "financing_cashflow"}
    })
    metrics["asset_liability_ratio"] = _safe_divide(metrics["total_liabilities"], metrics["total_assets"])
    metrics["ocf_to_net_profit"] = _safe_divide(metrics["operating_cashflow"], metrics["net_profit"])
    metrics["return_on_equity"] = _safe_divide(metrics["net_profit"], metrics["shareholders_equity"])
    localized_metrics = {FINANCIAL_METRIC_LABELS.get(key, key): value for key, value in metrics.items()}
    return latest_report_date, localized_metrics


async def get_financial_metrics(code: str) -> FinancialMetrics:
    """获取股票最新一期核心财务指标。

    Param:
        code: 股票代码
    Return:
        FinancialMetrics 模型对象，包含本地化字段名的指标字典
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key_no_day("financial_metrics", _FINANCIAL_CACHE_SCHEMA, sym.prefixed_upper)
    cached = cache.get(cache_key)
    if cached is not None:
        return FinancialMetrics.model_validate(cached)

    async def load_and_cache() -> FinancialMetrics:
        balance_rows, profit_rows, cashflow_rows = await asyncio.gather(
            get_financial(sym.raw, "balance"),
            get_financial(sym.raw, "profit"),
            get_financial(sym.raw, "cashflow"),
        )
        latest_report_date, metrics = _build_financial_metrics(
            pd.DataFrame(balance_rows),
            pd.DataFrame(profit_rows),
            pd.DataFrame(cashflow_rows),
        )
        result = FinancialMetrics(code=sym.raw, latest_report_date=latest_report_date, metrics=metrics)
        cache.set(cache_key, result, ttl=_FINANCIAL_CACHE_TTL_SECONDS)
        return result

    return await _financial_metrics_singleflight.do(cache_key, load_and_cache)
