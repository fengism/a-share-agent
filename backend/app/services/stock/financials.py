import asyncio

import pandas as pd

from app.constants.financial_labels import FINANCIAL_METRIC_ALIASES, FINANCIAL_METRIC_LABELS
from app.models.stock import FinancialMetrics
from app.services.providers import get_provider
from app.utils.cache import cache, dated_cache_key, dated_cache_key_no_day
from app.utils.rate_limiter import call_blocking, akshare_semaphore
from app.utils.data_clean import safe_float
from app.utils.symbol_utils import normalize_code


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


async def get_financial(code: str, indicator: str = "balance") -> list[dict]:
    """获取股票最近 4 期财报数据。

    Param:
        code: 股票代码
        indicator: 报表类型，balance/profit/cashflow 之一
    Return:
        财报字典列表，每项为一期数据
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key_no_day("financial", sym.prefixed_upper, indicator)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    df = await call_blocking(_get_akshare_provider().fetch_stock_financials, semaphore=akshare_semaphore, symbol=sym.prefixed_upper, indicator=indicator)
    df = df.head(4)
    result = df.fillna("N/A").to_dict(orient="records")
    cache.set(cache_key, result, ttl=86400)
    return result


_FINANCIAL_REPORT_DATE_COLUMNS = ["REPORT_DATE", "REPORT_DATE_NAME", "REPORT_DATE_NOTICE", "REPORT_DATE_ORG", "日期", "报告日期", "报告期"]


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


def _get_latest_financial_row(df: pd.DataFrame) -> tuple[pd.Series | None, str | None]:
    """提取财报 DataFrame 的最新行和对应报告期。

    Param:
        df: 财报 DataFrame
    Return:
        (最新行 Series, 报告期字符串) 元组
    """
    if df.empty:
        return None, None
    date_column = _find_report_date_column(df)
    row = df.iloc[0]
    report_date = _normalize_report_date(row.get(date_column)) if date_column else None
    return row, report_date


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
    balance_row, balance_report_date = _get_latest_financial_row(balance_df)
    profit_row, profit_report_date = _get_latest_financial_row(profit_df)
    cashflow_row, cashflow_report_date = _get_latest_financial_row(cashflow_df)

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
    latest_report_date = balance_report_date or profit_report_date or cashflow_report_date
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
    cache_key = dated_cache_key_no_day("financial_metrics", sym.prefixed_upper)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    balance_df, profit_df, cashflow_df = await asyncio.gather(
        call_blocking(_get_akshare_provider().fetch_stock_financials, semaphore=akshare_semaphore, symbol=sym.prefixed_upper, indicator="balance"),
        call_blocking(_get_akshare_provider().fetch_stock_financials, semaphore=akshare_semaphore, symbol=sym.prefixed_upper, indicator="profit"),
        call_blocking(_get_akshare_provider().fetch_stock_financials, semaphore=akshare_semaphore, symbol=sym.prefixed_upper, indicator="cashflow"),
    )
    latest_report_date, metrics = _build_financial_metrics(balance_df, profit_df, cashflow_df)
    result = FinancialMetrics(code=sym.raw, latest_report_date=latest_report_date, metrics=metrics)
    cache.set(cache_key, result, ttl=86400)
    return result
