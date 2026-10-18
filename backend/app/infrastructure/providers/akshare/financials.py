"""AkShare 财务与估值能力。"""

import pandas as pd

from app.configuration import get_settings
from app.constants.http import EASTMONEY_HEADERS
from app.infrastructure.http.client import get_provider_session
from app.infrastructure.http.proxy import ProxyScope, resolve_proxy_request
from app.infrastructure.providers.akshare.loader import ak

_VALUATION_COMPARISON_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
_VALUATION_COMPARISON_PROXY_SCOPE = ProxyScope(hosts=frozenset({"datacenter.eastmoney.com"}))
_VALUATION_COMPARISON_FIELDS = {
    "CORRE_SECURITY_CODE": "代码",
    "CORRE_SECURITY_NAME": "简称",
    "PE_TTM": "市盈率-TTM",
    "PE_1Y": "市盈率-25E",
    "PB_MRQ": "市净率-MRQ",
    "PS_TTM": "市销率-TTM",
}


def fetch_stock_financials(symbol: str, indicator: str) -> pd.DataFrame:
    if indicator == "balance":
        return ak.stock_balance_sheet_by_report_em(symbol=symbol)
    if indicator == "profit":
        return ak.stock_profit_sheet_by_report_em(symbol=symbol)
    if indicator == "cashflow":
        return ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
    raise ValueError(f"Unknown financial indicator: {indicator}")


def fetch_stock_valuation_comparison(symbol: str) -> pd.DataFrame:
    """获取东财同行估值比较表。

    AkShare 的封装会强制选择 EV/EBITDA 列，而银行等行业的接口不返回
    该字段，直接抛 KeyError，导致银行股完全拿不到 PE/PB 同行数据。
    这里在 AkShare 失败时直接请求同一接口，只保留估值所需字段。
    """
    try:
        return ak.stock_zh_valuation_comparison_em(symbol=symbol)
    except (KeyError, IndexError, TypeError, AttributeError):
        return _fetch_stock_valuation_comparison_resilient(symbol)


def _fetch_stock_valuation_comparison_resilient(symbol: str) -> pd.DataFrame:
    """绕过 AkShare 的强制列选择，直接解析东财原始响应。

    走共享 provider session 与运维代理作用域，避免在只配置了出站代理的
    环境里被这条回退路径绕开。
    """
    exchange, code = symbol[:2], symbol[2:]
    settings = get_settings()
    proxy_options = resolve_proxy_request(
        _VALUATION_COMPARISON_URL,
        settings,
        _VALUATION_COMPARISON_PROXY_SCOPE,
    )
    request_kwargs: dict = {
        "params": {
            "reportName": "RPT_PCF10_INDUSTRY_CVALUE",
            "columns": "ALL",
            "quoteColumns": "",
            "filter": f'(SECUCODE="{code}.{exchange}")',
            "pageNumber": "",
            "pageSize": "",
            "sortTypes": "1",
            "sortColumns": "PAIMING",
            "source": "HSF10",
            "client": "PC",
        },
        "headers": EASTMONEY_HEADERS,
        "timeout": proxy_options.timeout or 15,
    }
    if proxy_options.active:
        request_kwargs["proxies"] = proxy_options.proxies
    response = get_provider_session().get(_VALUATION_COMPARISON_URL, **request_kwargs)
    response.raise_for_status()
    rows = (response.json().get("result") or {}).get("data") or []
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame = frame.rename(
        columns={source: target for source, target in _VALUATION_COMPARISON_FIELDS.items() if source in frame.columns}
    )
    available = [column for column in _VALUATION_COMPARISON_FIELDS.values() if column in frame.columns]
    return frame[available]


VALID_BAIDU_VALUATION_INDICATORS = {
    "总市值",
    "市盈率(TTM)",
    "市盈率(静)",
    "市净率",
    "市现率",
}


def fetch_stock_valuation_baidu(
    symbol: str,
    indicator: str,
    period: str,
) -> pd.DataFrame:
    if indicator not in VALID_BAIDU_VALUATION_INDICATORS:
        return pd.DataFrame()
    try:
        df = ak.stock_zh_valuation_baidu(
            symbol=symbol,
            indicator=indicator,
            period=period,
        )
        if df is None or not isinstance(df, pd.DataFrame):
            return pd.DataFrame()
        return df
    except (KeyError, TypeError, IndexError, ValueError, AttributeError):
        return pd.DataFrame()
