"""沪深交易所 ETF 份额接口；份额统一为份，不包含业务 ETF 池筛选。"""

from __future__ import annotations

import io
import math
import random
import warnings
from datetime import date, datetime
from typing import cast

import httpx
import pandas as pd

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore

_SSE_URL = "https://query.sse.com.cn/commonQuery.do"
_SZSE_HISTORY_URL = "https://www.szse.cn/api/report/ShowReport"
_SZSE_CURRENT_URL = "https://fund.szse.cn/api/report/ShowReport"
_SZSE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
)


def _format_szse_date_param(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def _build_async_client(timeout: float | httpx.Timeout) -> httpx.AsyncClient:
    """创建绑定 IPv4 本地地址并直连的异步 HTTP 客户端，规避 IPv6 路由黑洞导致的握手超时。"""
    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        trust_env=False,
    )


async def fetch_sse_etf_shares(point_date: str) -> dict[str, float]:
    async with _build_async_client(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
        response = await client.get(
            _SSE_URL,
            params={
                "isPagination": "true",
                "pageHelp.pageSize": "1000",
                "pageHelp.pageNo": "1",
                "pageHelp.beginPage": "1",
                "pageHelp.cacheSize": "1",
                "pageHelp.endPage": "1",
                "sqlId": "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L",
                "STAT_DATE": point_date,
            },
            headers={"Referer": "https://www.sse.com.cn/", "User-Agent": "Mozilla/5.0"},
        )
    response.raise_for_status()
    rows = response.json().get("result") or []
    result: dict[str, float] = {}
    for row in rows:
        code = str(row.get("SEC_CODE", ""))
        try:
            shares = float(row["TOT_VOL"]) * 10_000
            if math.isfinite(shares) and shares >= 0:
                result[code] = shares
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _normalize_fund_code(value: object) -> str:
    raw = str(value).strip()
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    return raw.zfill(6)


def _parse_szse_current_frame(
    frame: pd.DataFrame,
    *,
    code_column: str,
    share_column: str,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for _, row in frame.iterrows():
        code = _normalize_fund_code(row.get(code_column, ""))
        if not (len(code) == 6 and code.isdigit()):
            continue
        try:
            raw_val = row[share_column]
            if isinstance(raw_val, (int, float)):
                shares = float(raw_val)
            else:
                shares = float(str(raw_val).replace(",", "").strip())
            if math.isfinite(shares) and shares >= 0:
                result[code] = shares
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _parse_szse_daily_history(
    frame: pd.DataFrame,
) -> tuple[dict[str, dict[str, float]], set[str]]:
    history: dict[str, dict[str, float]] = {}
    returned_dates: set[str] = set()
    for _, row in frame.iterrows():
        raw_date = row.get("日期")
        if isinstance(raw_date, datetime):
            point_date = raw_date.date().isoformat()
        elif isinstance(raw_date, date):
            point_date = raw_date.isoformat()
        else:
            try:
                point_date = datetime.fromisoformat(str(raw_date).strip()[:10]).date().isoformat()
            except ValueError:
                continue
        code = _normalize_fund_code(row.get("基金代码", ""))
        if not (len(code) == 6 and code.isdigit()):
            continue
        try:
            shares = float(row["基金份额"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(shares) and shares >= 0:
            history.setdefault(code, {})[point_date] = shares
            returned_dates.add(point_date)
    return history, returned_dates


async def fetch_szse_etf_share_history(
    start_date: str,
    end_date: str,
) -> tuple[dict[str, dict[str, float]], set[str]]:
    """直连深交所官方接口（不走代理）获取历史份额。"""
    headers = {
        "Host": "www.szse.cn",
        "Referer": "https://www.szse.cn/market/fund/volume/etf/index.html",
        "User-Agent": _SZSE_UA,
    }
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "scsj_fund_jjgm",
        "TABKEY": "tab1",
        "txtStart": _format_szse_date_param(start_date),
        "txtEnd": _format_szse_date_param(end_date),
        "jjlb": "ETF",
        "random": str(random.random()),
    }
    async with _build_async_client(timeout=10.0) as client:
        response = await client.get(_SZSE_HISTORY_URL, params=params, headers=headers)
        response.raise_for_status()
    return cast(
        tuple[dict[str, dict[str, float]], set[str]],
        await call_blocking(_parse_szse_history_content, response.content, semaphore=misc_semaphore),
    )


def _parse_szse_history_content(content: bytes) -> tuple[dict[str, dict[str, float]], set[str]]:
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        frame = pd.read_excel(io.BytesIO(content), engine="openpyxl")

    frame = frame.dropna(how="all").copy()
    if "基金规模(份)" in frame.columns:
        frame = frame.rename(columns={"基金规模(份)": "基金份额"})
    if "基金代码" in frame.columns:
        code_series = pd.to_numeric(frame["基金代码"], errors="coerce")
        frame = frame[code_series.notna()].copy()
        frame["基金代码"] = code_series[code_series.notna()].astype(int).astype(str).str.zfill(6)
    return _parse_szse_daily_history(frame)


async def fetch_szse_etf_current_shares() -> dict[str, float]:
    """直连深交所官方接口（不走代理）获取当前份额。"""
    headers = {
        "Referer": "https://fund.szse.cn/marketdata/fundslist/index.html",
        "User-Agent": _SZSE_UA,
    }
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "1000_lf",
        "TABKEY": "tab1",
        "random": str(random.random()),
    }
    async with _build_async_client(timeout=8.0) as client:
        response = await client.get(_SZSE_CURRENT_URL, params=params, headers=headers)
        response.raise_for_status()
    return cast(
        dict[str, float],
        await call_blocking(_parse_szse_current_content, response.content, semaphore=misc_semaphore),
    )


def _parse_szse_current_content(content: bytes) -> dict[str, float]:
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        frame = pd.read_excel(io.BytesIO(content), engine="openpyxl", dtype={"基金代码": str})
    frame = frame.rename(columns={"当前规模(份)": "基金份额"})
    return _parse_szse_current_frame(
        frame,
        code_column="基金代码",
        share_column="基金份额",
    )
