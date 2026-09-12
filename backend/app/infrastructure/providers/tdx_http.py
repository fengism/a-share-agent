"""通过独立 TDX HTTP 服务访问通达信数据。"""

import math
from bisect import bisect_right
from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd
import requests

from app.configuration import get_settings
from app.core.market import normalize_code, safe_float, safe_int, safe_string
from app.infrastructure.http.client import get_provider_session as get_session

_KLINE_COLUMNS = [
    "date",
    "open",
    "close",
    "high",
    "low",
    "volume",
    "amount",
    "pre_close",
    "turnover_pct",
]
_EQUITY_CHANGE_CATEGORIES = frozenset({2, 3, 5, 7, 8, 9, 10})


class TdxHttpAPIError(RuntimeError):
    pass


class TdxHttpUnavailableError(TdxHttpAPIError, ConnectionError):
    pass


def _tdx_price(value: Any) -> float | None:
    parsed = safe_float(value, scale=1000)
    return float(parsed) if parsed is not None else None


def _date_number(value: Any) -> str | None:
    number = safe_float(value)
    if number is None or not math.isfinite(number) or number <= 0:
        return None
    return f"{int(number):08d}"


def _parse_equity_history(payload: Any) -> tuple[list[date], list[float]]:
    """Parse TDX GBBQ records into effective dates and float shares."""
    if not isinstance(payload, dict) or not isinstance(payload.get("List"), list):
        raise TdxHttpAPIError("TDX HTTP 股本变更响应结构无效")

    events: list[tuple[date, float]] = []
    for item in payload["List"]:
        if not isinstance(item, dict):
            continue
        category = safe_int(item.get("Category"))
        float_shares = safe_float(item.get("C3"))
        parsed_time = pd.to_datetime(item.get("Time"), errors="coerce")
        if (
            category not in _EQUITY_CHANGE_CATEGORIES
            or float_shares is None
            or not math.isfinite(float_shares)
            or float_shares <= 0
            or pd.isna(parsed_time)
        ):
            continue
        events.append((parsed_time.date(), float_shares))

    events.sort(key=lambda event: event[0])
    return [event[0] for event in events], [event[1] for event in events]


class TdxHttpDataProvider:
    """TDX REST API 适配器。"""

    name = "tdx_http"

    def __init__(
        self,
        session: requests.Session | None = None,
        settings_provider: Callable[[], Any] = get_settings,
    ):
        self._provided_session = session
        self._settings_provider = settings_provider

    @property
    def _session(self) -> requests.Session:
        return self._provided_session or get_session()

    def _request(self, path: str, params: dict[str, str] | None = None) -> Any:
        settings = self._settings_provider()
        if not settings.tdx_http_enabled:
            raise TdxHttpAPIError("TDX HTTP 数据源未启用")
        base_url = str(settings.tdx_http_base_url).rstrip("/")
        if not base_url:
            raise TdxHttpAPIError("TDX HTTP BASE URL 为空")
        response = self._session.get(
            f"{base_url}{path}",
            params=params,
            timeout=float(settings.tdx_http_timeout_seconds),
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise TdxHttpAPIError(f"TDX HTTP 返回非 JSON 响应: {path}") from exc
        if not isinstance(payload, dict):
            raise TdxHttpAPIError(f"TDX HTTP 响应结构无效: {path}")
        if payload.get("code") != 0:
            message = safe_string(payload.get("msg")) or "未知错误"
            raise TdxHttpUnavailableError(f"TDX HTTP 请求失败: {message}")
        return payload.get("data")

    def fetch_stock_names(self) -> list[dict[str, str]]:
        """获取 A 股代码与名称。"""
        raw_stock_codes = self._request("/code/stocks")
        if not isinstance(raw_stock_codes, list):
            raise TdxHttpAPIError("TDX HTTP 股票代码列表结构无效")
        stock_codes = {str(code).strip().lower() for code in raw_stock_codes}
        stocks: dict[str, str] = {}
        for exchange in ("sh", "sz", "bj"):
            payload = self._request("/code/all", params={"exchange": exchange})
            if not isinstance(payload, dict) or not isinstance(payload.get("List"), list):
                raise TdxHttpAPIError(f"TDX HTTP {exchange.upper()} 名称列表结构无效")
            for item in payload["List"]:
                if not isinstance(item, dict):
                    continue
                code = safe_string(item.get("Code"))
                name = safe_string(item.get("Name"))
                if code is None or name is None or f"{exchange}{code}".lower() not in stock_codes:
                    continue
                stocks[code] = name
        return [{"code": code, "name": stocks[code]} for code in sorted(stocks)]

    def fetch_stock_kline(
        self,
        code: str,
        start_date: str = "",
        end_date: str = "",
        adjust: str = "qfq",
        include_turnover: bool = False,
    ) -> pd.DataFrame:
        """获取日 K 线，并按需使用历史流通股本计算换手率。"""
        symbol = normalize_code(code)
        normalized_start = start_date.strip().replace("-", "")
        normalized_end = end_date.strip().replace("-", "")
        params = {
            "code": symbol.prefixed_lower,
            "adjust": adjust or "none",
        }
        if normalized_start:
            params["since"] = normalized_start
        payload = self._request("/kline/day/all", params=params)
        if not isinstance(payload, dict) or not isinstance(payload.get("List"), list):
            raise TdxHttpAPIError("TDX HTTP 日 K 线响应结构无效")

        end_boundary = pd.to_datetime(normalized_end, format="%Y%m%d", errors="coerce") if normalized_end else None
        rows: list[dict[str, Any]] = []
        trading_dates: list[date] = []
        for item in payload["List"]:
            if not isinstance(item, dict):
                continue
            parsed_date = pd.to_datetime(item.get("Time"), errors="coerce")
            if pd.isna(parsed_date):
                continue
            trading_date = parsed_date.date()
            if end_boundary is not None and trading_date > end_boundary.date():
                continue
            volume = safe_float(item.get("Volume"))
            if volume is not None and (not math.isfinite(volume) or volume < 0):
                volume = None
            rows.append(
                {
                    "date": parsed_date.strftime("%Y-%m-%d"),
                    "open": safe_float(item.get("Open"), scale=1000),
                    "close": safe_float(item.get("Close"), scale=1000),
                    "high": safe_float(item.get("High"), scale=1000),
                    "low": safe_float(item.get("Low"), scale=1000),
                    "volume": volume,
                    "amount": safe_float(item.get("Amount"), scale=1000),
                    "pre_close": safe_float(item.get("Last"), scale=1000),
                    "turnover_pct": None,
                }
            )
            trading_dates.append(trading_date)
        if not rows:
            return pd.DataFrame(columns=_KLINE_COLUMNS)

        if include_turnover:
            equity_payload = self._request("/gbbq", params={"code": symbol.prefixed_lower})
            equity_dates, float_shares = _parse_equity_history(equity_payload)
            for row, trading_date in zip(rows, trading_dates, strict=True):
                volume = row["volume"]
                if volume is None:
                    continue
                equity_index = bisect_right(equity_dates, trading_date) - 1
                if equity_index < 0:
                    continue
                # TDX K 线成交量单位为手，GBBQ C3 的流通股本单位为股。
                turnover_pct = volume * 10_000 / float_shares[equity_index]
                if math.isfinite(turnover_pct) and turnover_pct >= 0:
                    row["turnover_pct"] = turnover_pct
        return pd.DataFrame(rows, columns=_KLINE_COLUMNS).sort_values("date").reset_index(drop=True)

    def fetch_stock_quotes(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        """批量获取标准化实时行情。"""
        symbols = [normalize_code(code) for code in dict.fromkeys(codes)]
        if not symbols:
            return {}
        requested_codes = {symbol.raw for symbol in symbols}
        payload = self._request(
            "/quote",
            params={"codes": ",".join(symbol.prefixed_lower for symbol in symbols)},
        )
        if not isinstance(payload, list):
            raise TdxHttpAPIError("TDX HTTP 实时行情响应结构无效")

        quotes: dict[str, dict[str, Any]] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            code = safe_string(item.get("Code"))
            kline = item.get("Kline")
            if code not in requested_codes or not isinstance(kline, dict):
                continue
            price = _tdx_price(kline.get("Close"))
            last_close = _tdx_price(kline.get("Last"))
            high = _tdx_price(kline.get("High"))
            low = _tdx_price(kline.get("Low"))
            change_amount = round(price - last_close, 3) if price is not None and last_close is not None else None
            change_pct = (
                (price - last_close) / last_close * 100
                if price is not None and last_close not in (None, 0)
                else None
            )
            amplitude_pct = (
                (high - low) / last_close * 100
                if high is not None and low is not None and last_close not in (None, 0)
                else None
            )
            quotes[code] = {
                "code": code,
                "price": price,
                "last_close": last_close,
                "open": _tdx_price(kline.get("Open")),
                "high": high,
                "low": low,
                "change_amt": change_amount,
                "change_pct": change_pct,
                "amplitude_pct": amplitude_pct,
                "volume": safe_float(kline.get("Volume")),
                "amount": _tdx_price(kline.get("Amount")),
                "quoted_at": safe_string(kline.get("Time")),
            }
        return quotes

    def fetch_stock_quote(self, code: str) -> dict[str, Any]:
        """获取单只股票的标准化实时行情。"""
        normalized = normalize_code(code).raw
        return self.fetch_stock_quotes([normalized]).get(normalized, {})

    def fetch_finance_info(self, code: str) -> dict[str, Any]:
        """获取上市日期及股本等基础财务字段。"""
        symbol = normalize_code(code)
        payload = self._request(
            "/finance",
            params={"exchange": symbol.exchange.lower(), "code": symbol.raw},
        )
        if not isinstance(payload, dict):
            raise TdxHttpAPIError("TDX HTTP 财务信息响应结构无效")
        return {
            "list_date": _date_number(payload.get("IPODate")),
            "updated_date": _date_number(payload.get("UpdatedDate")),
            "total_shares": safe_float(payload.get("ZongGuBen")),
            "float_shares": safe_float(payload.get("LiuTongGuBen")),
        }


tdx_http_provider = TdxHttpDataProvider()
