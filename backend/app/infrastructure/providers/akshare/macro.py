"""AKShare China and US macro adapters."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

import pandas as pd

from app.infrastructure.providers.akshare.loader import ak

AKSHARE_MACRO_API = "https://akshare.akfamily.xyz/data/macro/macro.html"


def _date_text(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _event_series(loader: Callable[[], pd.DataFrame]) -> dict[str, float]:
    frame = loader()
    if frame is None or frame.empty:
        return {}
    date_col = next((col for col in ("时间", "日期", "发布日期") if col in frame.columns), None)
    value_col = next((col for col in ("现值", "今值") if col in frame.columns), None)
    if date_col is None or value_col is None:
        return {}
    result: dict[str, float] = {}
    for _, row in frame.iterrows():
        date = _date_text(row.get(date_col))
        value = pd.to_numeric(row.get(value_col), errors="coerce")
        if date and pd.notna(value):
            result[date] = float(value)
    return result


def _parallel_event_series(
    loaders: dict[str, Callable[[], pd.DataFrame]],
) -> dict[str, dict[str, float]]:
    with ThreadPoolExecutor(max_workers=max(1, len(loaders)), thread_name_prefix="akshare-macro") as executor:
        futures = {field: executor.submit(_event_series, loader) for field, loader in loaders.items()}
        return {field: future.result() for field, future in futures.items()}


def _combined_rows(
    series: dict[str, dict[str, float]],
    *,
    carry_forward: bool = False,
) -> list[dict[str, Any]]:
    periods = sorted(set().union(*(values.keys() for values in series.values())))
    latest: dict[str, float] = {}
    latest_periods: dict[str, str] = {}
    rows = []
    for period in periods:
        values_for_period = {}
        for field, values in series.items():
            if period in values:
                latest[field] = values[period]
                latest_periods[field] = period
            values_for_period[field] = latest.get(field) if carry_forward else values.get(period)
        row = {"TIME": period, **values_for_period}
        if carry_forward:
            row["_FIELD_PERIODS"] = dict(latest_periods)
        rows.append(row)
    return list(reversed(rows))


def fetch_china_cpi() -> list[dict[str, Any]]:
    return _combined_rows({
        "NATIONAL_SAME": _event_series(ak.macro_china_cpi_yearly),
        "NATIONAL_SEQUENTIAL": _event_series(ak.macro_china_cpi_monthly),
    })


def fetch_china_ppi() -> list[dict[str, Any]]:
    yoy = _event_series(ak.macro_china_ppi_yearly)
    return _combined_rows({"BASE": yoy, "BASE_SAME": yoy})


def fetch_china_pmi() -> list[dict[str, Any]]:
    return _combined_rows({
        "MAKE_INDEX": _event_series(ak.macro_china_pmi_yearly),
        "NMAKE_INDEX": _event_series(ak.macro_china_non_man_pmi),
    })


def fetch_china_economy_currency_supply() -> list[dict[str, Any]]:
    frame = ak.macro_china_money_supply()
    if frame is None or frame.empty:
        return []
    mapping = {
        "月份": "TIME",
        "货币和准货币(M2)-数量(亿元)": "BASIC_CURRENCY",
        "货币和准货币(M2)-同比增长": "BASIC_CURRENCY_SAME",
        "货币(M1)-数量(亿元)": "CURRENCY",
        "货币(M1)-同比增长": "CURRENCY_SAME",
        "流通中的现金(M0)-数量(亿元)": "FREE_CASH",
        "流通中的现金(M0)-同比增长": "FREE_CASH_SAME",
    }
    return cast(list[dict[str, Any]], frame.rename(columns=mapping)[list(mapping.values())].head(24).to_dict("records"))


def fetch_china_gdp() -> list[dict[str, Any]]:
    frame = ak.macro_china_gdp()
    if frame is None or frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    cumulative: dict[tuple[int, int], float] = {}
    for _, row in frame.iterrows():
        text = str(row.get("季度") or "")
        match = pd.Series([text]).str.extract(r"(\d{4})年第1(?:-(\d))?季度").iloc[0]
        if pd.isna(match.iloc[0]):
            continue
        year = int(match.iloc[0])
        quarter = int(match.iloc[1]) if pd.notna(match.iloc[1]) else 1
        value = pd.to_numeric(row.get("国内生产总值-绝对值"), errors="coerce")
        growth = pd.to_numeric(row.get("国内生产总值-同比增长"), errors="coerce")
        if pd.isna(value):
            continue
        cumulative[(year, quarter)] = float(value)
        rows.append({
            "TIME": f"{year}Q{quarter}",
            "YEAR": year,
            "QUARTER": quarter,
            "CUMULATIVE": float(value),
            "SUM_SAME": None if pd.isna(growth) else float(growth),
        })
    normalized = [
        {
            "TIME": row["TIME"],
            "DOMESTICL_PRODUCT_BASE": round(
                row["CUMULATIVE"] - cumulative.get((row["YEAR"], row["QUARTER"] - 1), 0.0),
                6,
            ),
            "SUM_SAME": row["SUM_SAME"],
        }
        for row in rows
    ]
    return sorted(normalized, key=lambda item: item["TIME"], reverse=True)[:12]


def fetch_china_lpr() -> list[dict[str, Any]]:
    frame = ak.macro_china_lpr()
    if frame is None or frame.empty:
        return []
    return cast(list[dict[str, Any]], frame.sort_values("TRADE_DATE", ascending=False).head(20).assign(
        TIME=lambda value: value["TRADE_DATE"].astype(str)
    ).to_dict("records"))


def fetch_china_shibor() -> list[dict[str, Any]]:
    frame = ak.macro_china_shibor_all()
    if frame is None or frame.empty:
        return []
    rows = []
    for _, row in frame.tail(20).iloc[::-1].iterrows():
        for period, column in (("O/N", "O/N-定价"), ("1W", "1W-定价"), ("1M", "1M-定价"), ("3M", "3M-定价"), ("6M", "6M-定价"), ("9M", "9M-定价"), ("1Y", "1Y-定价")):
            value = pd.to_numeric(row.get(column), errors="coerce")
            if pd.notna(value):
                rows.append({"REPORT_DATE": str(row.get("日期")), "REPORT_PERIOD": period, "IR_RATE": float(value), "MARKET_CODE": "001", "CURRENCY_CODE": "CNY"})
    return rows


def fetch_china_social_financing() -> list[dict[str, Any]]:
    frame = ak.macro_china_shrzgm()
    if frame is None or frame.empty:
        return []
    return [
        {"TIME": str(row.get("月份")), "RMB_LOAN": row.get("其中-人民币贷款"), "RMB_LOAN_ACCUMULATE": row.get("社会融资规模增量")}
        for _, row in frame.tail(24).iloc[::-1].iterrows()
    ]


def fetch_china_trade() -> list[dict[str, Any]]:
    return _combined_rows({
        "EXIT_BASE_SAME": _event_series(ak.macro_china_exports_yoy),
        "IMPORT_BASE_SAME": _event_series(ak.macro_china_imports_yoy),
        "BALANCE_DIRECT": _event_series(ak.macro_china_trade_balance),
    })


def _us_indicator(loader: Callable[[], pd.DataFrame], value_key: str = "VALUE") -> list[dict[str, Any]]:
    values = _event_series(loader)
    return [{"TIME": period, value_key: value} for period, value in sorted(values.items(), reverse=True)[:24]]


def fetch_us_gdp() -> list[dict[str, Any]]:
    return _us_indicator(ak.macro_usa_gdp_monthly)


def fetch_us_ppi() -> list[dict[str, Any]]:
    return _combined_rows(_parallel_event_series({
        "PPI_MOM": ak.macro_usa_ppi,
        "CORE_PPI_MOM": ak.macro_usa_core_ppi,
    }), carry_forward=True)[:24]


def fetch_us_cpi() -> list[dict[str, Any]]:
    return _combined_rows(_parallel_event_series({
        "CPI_YOY": ak.macro_usa_cpi_yoy,
        "CPI_MOM": ak.macro_usa_cpi_monthly,
        "CORE_CPI_MOM": ak.macro_usa_core_cpi_monthly,
    }), carry_forward=True)[:24]


def fetch_us_labor() -> list[dict[str, Any]]:
    return _combined_rows(_parallel_event_series({
        "UNEMPLOYMENT": ak.macro_usa_unemployment_rate,
        "NON_FARM": ak.macro_usa_non_farm,
        "INITIAL_JOBLESS": ak.macro_usa_initial_jobless,
    }), carry_forward=True)[:24]


def fetch_us_pmi() -> list[dict[str, Any]]:
    return _combined_rows(_parallel_event_series({
        "MANUFACTURING_PMI": ak.macro_usa_ism_pmi,
        "SERVICES_PMI": ak.macro_usa_services_pmi,
    }), carry_forward=True)[:24]


def fetch_us_fed_rate() -> list[dict[str, Any]]:
    return _us_indicator(ak.macro_bank_usa_interest_rate)


def fetch_us_retail_sales() -> list[dict[str, Any]]:
    return _us_indicator(ak.macro_usa_retail_sales)


def fetch_us_trade_balance() -> list[dict[str, Any]]:
    return _us_indicator(ak.macro_usa_trade_balance)
