import logging
from collections.abc import Callable, Mapping

ExtractLatest = Callable[[list[dict], list[str]], dict | None]
ExtractRecent = Callable[[list[dict], list[str], int], list[dict]]

_CPI_KEYS = ["TIME", "NATIONAL_SAME", "NATIONAL_SEQUENTIAL", "NATIONAL_ACCUMULATE"]
_PPI_KEYS = ["TIME", "BASE", "BASE_SAME", "BASE_ACCUMULATE"]
_PMI_KEYS = ["TIME", "MAKE_INDEX", "MAKE_SAME", "NMAKE_INDEX", "NMAKE_SAME"]
_MONEY_SUPPLY_KEYS = [
    "TIME",
    "BASIC_CURRENCY",
    "BASIC_CURRENCY_SAME",
    "CURRENCY",
    "CURRENCY_SAME",
    "FREE_CASH",
    "FREE_CASH_SAME",
]
_SOCIAL_FINANCING_KEYS = [
    "TIME",
    "SOCIAL_FINANCING_INCREMENT",
    "RMB_LOAN_ACCUMULATE",
    "RMB_LOAN",
    "RMB_LOAN_SAME",
    "RMB_LOAN_SEQUENTIAL",
    "LOAN_ACCUMULATE_SAME",
    "FX_LOAN",
    "ENTRUSTED_LOAN",
    "TRUST_LOAN",
    "UNDISCOUNTED_BANKERS_ACCEPTANCE",
    "CORPORATE_BOND",
    "GOVERNMENT_BOND",
    "EQUITY_FINANCING",
    "ABS_BY_DEPOSITORY",
    "LOANS_WRITTEN_OFF",
]
_INDUSTRIAL_PRODUCTION_KEYS = [
    "TIME",
    "VALUE_ADDED_YOY",
    "VALUE_ADDED_ACCUMULATE_YOY",
]
_RETAIL_SALES_KEYS = [
    "TIME",
    "RETAIL_VALUE",
    "RETAIL_YOY",
    "RETAIL_ACCUMULATE",
    "RETAIL_ACCUMULATE_YOY",
]
_FIXED_ASSET_INVESTMENT_KEYS = ["TIME", "INVESTMENT_ACCUMULATE_YOY"]
_REAL_ESTATE_KEYS = [
    "TIME",
    "DEVELOPMENT_INVESTMENT",
    "DEVELOPMENT_INVESTMENT_YOY",
    "SALES_AREA",
    "SALES_AREA_YOY",
    "SALES_VALUE",
    "SALES_VALUE_YOY",
]
_EMPLOYMENT_KEYS = [
    "TIME",
    "URBAN_SURVEYED_UNEMPLOYMENT",
    "CITY31_SURVEYED_UNEMPLOYMENT",
]
_SHIBOR_PERIODS = {
    "隔夜": "ON",
    "O/N": "ON",
    "1周": "WEEK1",
    "1W": "WEEK1",
    "2周": "WEEK2",
    "2W": "WEEK2",
    "1月": "MONTH1",
    "1M": "MONTH1",
    "3月": "MONTH3",
    "3M": "MONTH3",
    "4月": "MONTH4",
    "4M": "MONTH4",
    "6月": "MONTH6",
    "6M": "MONTH6",
    "9月": "MONTH9",
    "9M": "MONTH9",
    "1年": "YEAR1",
    "1Y": "YEAR1",
}


def extract_latest(data: list[dict], keys: list[str]) -> dict | None:
    if not data:
        return None
    row = data[0]
    return {key: row.get(key) for key in keys if row.get(key) is not None}


def extract_recent(data: list[dict], keys: list[str], count: int = 3) -> list[dict]:
    results = []
    for row in data[:count]:
        item = {key: row.get(key) for key in keys if row.get(key) is not None}
        if item:
            results.append(item)
    return results


def _source_metadata(value: object) -> dict:
    if not isinstance(value, list) or not value or not isinstance(value[0], dict):
        return {}
    row = value[0]
    return {
        "source": row.get("_SOURCE"),
        "source_api": row.get("_SOURCE_API"),
        "latest_period": row.get("_LATEST_PERIOD"),
        "is_fallback": bool(row.get("_IS_FALLBACK", False)),
        "is_stale": bool(row.get("_IS_STALE", False)),
        "field_periods": dict(row.get("_FIELD_PERIODS") or {}),
        "stale_fields": list(row.get("_STALE_FIELDS") or []),
    }


def _series(
    value: object,
    keys: list[str],
    count: int,
    label: str,
    logger: logging.Logger,
    extract_latest_func: ExtractLatest,
    extract_recent_func: ExtractRecent,
) -> dict:
    if isinstance(value, list) and value:
        return {
            "latest": extract_latest_func(value, keys),
            "trend": extract_recent_func(value, keys, count),
            **_source_metadata(value),
        }
    if isinstance(value, Exception):
        logger.warning("%s 数据获取失败: %s", label, value)
    return {"latest": None, "trend": []}


def normalize_basic(
    collected: Mapping[str, object],
    logger: logging.Logger,
    extract_latest_func: ExtractLatest = extract_latest,
    extract_recent_func: ExtractRecent = extract_recent,
) -> dict:
    return {
        "cpi": _series(
            collected.get("cpi"),
            _CPI_KEYS,
            3,
            "CPI",
            logger,
            extract_latest_func,
            extract_recent_func,
        ),
        "ppi": _series(
            collected.get("ppi"),
            _PPI_KEYS,
            3,
            "PPI",
            logger,
            extract_latest_func,
            extract_recent_func,
        ),
        "pmi": _series(
            collected.get("pmi"),
            _PMI_KEYS,
            3,
            "PMI",
            logger,
            extract_latest_func,
            extract_recent_func,
        ),
        "money_supply": _series(
            collected.get("money_supply"),
            _MONEY_SUPPLY_KEYS,
            3,
            "货币供应量",
            logger,
            extract_latest_func,
            extract_recent_func,
        ),
    }


def _normalize_shibor(rows: list[dict]) -> tuple[list[dict], list[str]]:
    date_rows: dict[str, dict] = {}
    for row in rows:
        if row.get("MARKET_CODE") != "001" or row.get("CURRENCY_CODE") != "CNY":
            continue
        date = str(row.get("REPORT_DATE", ""))[:10]
        period = str(row.get("REPORT_PERIOD", ""))
        rate = row.get("IR_RATE")
        column = next((name for keyword, name in _SHIBOR_PERIODS.items() if keyword in period), None)
        if column and rate is not None:
            date_rows.setdefault(date, {"TIME": date})[column] = rate
    pivoted = sorted(date_rows.values(), key=lambda item: item["TIME"], reverse=True)
    columns = sorted({key for row in pivoted for key in row if key != "TIME"})
    return pivoted, ["TIME", *columns]


def _normalize_gdp(rows: list[dict]) -> list[dict]:
    return [
        {
            "TIME": row.get("TIME"),
            "GDP_VALUE": row.get("DOMESTICL_PRODUCT_BASE"),
            "GDP_SAME": row.get("SUM_SAME"),
        }
        for row in rows
    ]


def _normalize_trade(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        exports = row.get("EXIT_BASE")
        imports = row.get("IMPORT_BASE")
        balance = None
        if exports is not None and imports is not None:
            try:
                balance = round((exports - imports) / 100000, 2)
            except (TypeError, ValueError):
                balance = None
        normalized.append(
            {
                "TIME": row.get("TIME"),
                "EXPORTS_SAME": row.get("EXIT_BASE_SAME"),
                "IMPORTS_SAME": row.get("IMPORT_BASE_SAME"),
                "BALANCE": balance,
            }
        )
    return normalized


def normalize_full(
    collected: Mapping[str, object],
    logger: logging.Logger,
    extract_latest_func: ExtractLatest = extract_latest,
    extract_recent_func: ExtractRecent = extract_recent,
) -> dict:
    prices = {
        "cpi": _series(
            collected.get("cpi"),
            _CPI_KEYS,
            12,
            "CPI",
            logger,
            extract_latest_func,
            extract_recent_func,
        ),
        "ppi": _series(
            collected.get("ppi"),
            _PPI_KEYS,
            12,
            "PPI",
            logger,
            extract_latest_func,
            extract_recent_func,
        ),
    }
    sentiment = {
        "pmi": _series(
            collected.get("pmi"),
            _PMI_KEYS,
            12,
            "PMI",
            logger,
            extract_latest_func,
            extract_recent_func,
        )
    }
    monetary = {
        "money_supply": _series(
            collected.get("money_supply"),
            _MONEY_SUPPLY_KEYS,
            12,
            "货币供应量",
            logger,
            extract_latest_func,
            extract_recent_func,
        ),
        "social_financing": _series(
            collected.get("social_financing"),
            _SOCIAL_FINANCING_KEYS,
            12,
            "社会融资",
            logger,
            extract_latest_func,
            extract_recent_func,
        ),
    }
    rates = {
        "lpr": _series(
            collected.get("lpr"),
            ["TIME", "LPR1Y", "LPR5Y"],
            12,
            "LPR",
            logger,
            extract_latest_func,
            extract_recent_func,
        )
    }

    shibor_data = collected.get("shibor")
    if isinstance(shibor_data, list) and shibor_data:
        shibor_rows, shibor_columns = _normalize_shibor(shibor_data)
        rates["shibor"] = {
            "latest": extract_latest_func(shibor_rows, shibor_columns),
            "trend": extract_recent_func(shibor_rows, shibor_columns, 12),
            **_source_metadata(shibor_data),
        }
    else:
        rates["shibor"] = {"latest": None, "trend": []}
        if isinstance(shibor_data, Exception):
            logger.warning("SHIBOR 数据获取失败: %s", shibor_data)

    gdp_data = collected.get("gdp")
    if isinstance(gdp_data, list) and gdp_data:
        gdp_rows = _normalize_gdp(gdp_data)
        growth = {
            "gdp": {
                "latest": extract_latest_func(gdp_rows, ["TIME", "GDP_VALUE", "GDP_SAME"]),
                "trend": extract_recent_func(gdp_rows, ["TIME", "GDP_VALUE", "GDP_SAME"], 12),
                **_source_metadata(gdp_data),
            }
        }
    else:
        growth = {"gdp": {"latest": None, "trend": []}}
        if isinstance(gdp_data, Exception):
            logger.warning("GDP 数据获取失败: %s", gdp_data)

    growth.update(
        {
            "industrial_production": _series(
                collected.get("industrial_production"),
                _INDUSTRIAL_PRODUCTION_KEYS,
                12,
                "规模以上工业增加值",
                logger,
                extract_latest_func,
                extract_recent_func,
            ),
            "retail_sales": _series(
                collected.get("retail_sales"),
                _RETAIL_SALES_KEYS,
                12,
                "社会消费品零售总额",
                logger,
                extract_latest_func,
                extract_recent_func,
            ),
            "fixed_asset_investment": _series(
                collected.get("fixed_asset_investment"),
                _FIXED_ASSET_INVESTMENT_KEYS,
                12,
                "固定资产投资",
                logger,
                extract_latest_func,
                extract_recent_func,
            ),
            "real_estate": _series(
                collected.get("real_estate"),
                _REAL_ESTATE_KEYS,
                12,
                "房地产开发与销售",
                logger,
                extract_latest_func,
                extract_recent_func,
            ),
            "employment": _series(
                collected.get("employment"),
                _EMPLOYMENT_KEYS,
                12,
                "城镇调查失业率",
                logger,
                extract_latest_func,
                extract_recent_func,
            ),
        }
    )

    trade_data = collected.get("trade")
    if isinstance(trade_data, list) and trade_data:
        trade_rows = _normalize_trade(trade_data)
        trade = {
            "exports_imports": {
                "latest": extract_latest_func(trade_rows, ["TIME", "EXPORTS_SAME", "IMPORTS_SAME"]),
                "trend": extract_recent_func(trade_rows, ["TIME", "EXPORTS_SAME", "IMPORTS_SAME"], 12),
                **_source_metadata(trade_data),
            },
            "balance": {
                "latest": extract_latest_func(trade_rows, ["TIME", "BALANCE"]),
                "trend": extract_recent_func(trade_rows, ["TIME", "BALANCE"], 12),
                **_source_metadata(trade_data),
            },
        }
    else:
        trade = {
            "exports_imports": {"latest": None, "trend": []},
            "balance": {"latest": None, "trend": []},
        }
        if isinstance(trade_data, Exception):
            logger.warning("外贸数据获取失败: %s", trade_data)

    return {
        "prices": prices,
        "sentiment": sentiment,
        "monetary": monetary,
        "rates": rates,
        "growth": growth,
        "trade": trade,
    }


def normalize_generic(
    value: object,
    keys: list[str],
    count: int,
    label: str,
    logger: logging.Logger,
) -> dict:
    return _series(value, keys, count, label, logger, extract_latest, extract_recent)
