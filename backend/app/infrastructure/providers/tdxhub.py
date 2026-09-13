"""通过 tdxhub-sdk 进程内直连通达信行情与财务数据。

替代原 mootdx 直连与 tdx-api HTTP sidecar 两条链路：
底层统一走共享的 tdxhub StdQuotes 客户端。
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd
from tdxhub.consts import MARKET_BJ
from tdxhub.exceptions import TdxhubConnectionError
from tdxhub.quotes import Quotes
from tdxpy.parser.std.get_security_quotes import GetSecurityQuotesCmd

from app.configuration import get_settings
from app.core.market import normalize_code, safe_float, safe_string

logger = logging.getLogger(__name__)

_DAILY_FREQUENCY = 9
# TDX 协议单次行情快照的代码数量上限
_QUOTES_BATCH_SIZE = 80
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


class TdxhubError(RuntimeError):
    pass


class TdxhubUnavailableError(TdxhubError, ConnectionError):
    pass


class SharedTdxhubQuotes:
    """进程内共享的 tdxhub 行情客户端。

    tdxpy 底层 TCP 客户端非线程安全，所有调用经统一锁串行化（上游
    tdx_semaphore 已将并发限制为 2，串行化与原 tdx-api 池大小 1 相当）；
    连接类异常时重建客户端并重试一次。
    """

    def __init__(self, settings_provider: Callable[[], Any] = get_settings):
        self._settings_provider = settings_provider
        self._lock = threading.Lock()
        self._client = None

    def _new_client(self):
        timeout = float(self._settings_provider().tdxhub_timeout_seconds)
        return Quotes.factory(market="std", timeout=timeout)

    def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        def invoke(client):
            return getattr(client, method)(*args, **kwargs)

        return self._invoke_with_retry(invoke)

    def security_quotes_raw(self, market_code_pairs: list[tuple[int, str]]) -> Any:
        """直接走 GetSecurityQuotesCmd 协议命令获取行情快照。

        tdxpy 的 get_security_quotes 在客户端硬编码拒绝北交所(market=2)，
        但协议本身支持（与原 tdx-api 行为一致），此处绕过该守卫。
        """

        def invoke(client):
            api = client.client
            # tdxpy 的证券类型表不识别 market=2，会记一条 ERROR 后按默认
            # 价格系数 0.01 兜底（对北交所正确）。调用窗口内静音该噪音日志；
            # 所有调用均在共享锁内串行，临时调整日志级别无并发问题。
            tdxpy_logger = logging.getLogger("tdxpy")
            original_level = tdxpy_logger.level
            tdxpy_logger.setLevel(logging.CRITICAL)
            try:
                cmd = GetSecurityQuotesCmd(api.client, lock=api.lock)
                cmd.setParams(market_code_pairs)
                return cmd.call_api()
            finally:
                tdxpy_logger.setLevel(original_level)

        return self._invoke_with_retry(invoke)

    def _invoke_with_retry(self, invoke: Callable[[Any], Any]) -> Any:
        with self._lock:
            if self._client is None:
                self._client = self._acquire_client()
            try:
                return invoke(self._client)
            except (TdxhubConnectionError, ConnectionError, OSError, TimeoutError) as exc:
                logger.warning("tdxhub 连接异常，重建客户端后重试: %s", exc)
                self._client = None
                self._client = self._acquire_client()
                return invoke(self._client)

    def _acquire_client(self):
        try:
            return self._new_client()
        except (TdxhubConnectionError, ConnectionError, OSError, TimeoutError) as exc:
            raise TdxhubUnavailableError("TDX 行情服务器连接不可用") from exc

    def reset(self) -> None:
        """丢弃当前客户端，下次调用时重建，供异常恢复与测试隔离使用。"""
        with self._lock:
            self._client = None


shared_tdxhub_quotes = SharedTdxhubQuotes()


class TdxhubDataProvider:
    """通达信数据适配器：股票名称、K线、实时行情与财务基础信息。"""

    name = "tdxhub"

    def __init__(self, quotes: SharedTdxhubQuotes | None = None):
        self._quotes = quotes or shared_tdxhub_quotes

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return self._quotes.call(method, *args, **kwargs)

    @staticmethod
    def _directory_frame(frame: Any) -> pd.DataFrame | None:
        return frame if isinstance(frame, pd.DataFrame) and not frame.empty else None

    def fetch_stock_names(self) -> list[dict[str, str]]:
        """获取沪深京 A 股代码与名称。"""
        frame = self._directory_frame(self._call("stock_all", security_type="a_stock"))
        if frame is None:
            raise TdxhubError("TDX 股票名称列表为空")
        code_column = "code" if "code" in frame.columns else frame.columns[0]
        name_column = "name" if "name" in frame.columns else frame.columns[1]
        stocks: dict[str, str] = {}
        for code, name in zip(frame[code_column], frame[name_column], strict=True):
            raw_code = safe_string(code)
            raw_name = safe_string(name)
            if raw_code is None or raw_name is None:
                continue
            # 通达信名称为定宽字段，尾部以 \x00 填充
            stocks[raw_code.zfill(6)] = raw_name.strip("\x00 ").strip()
        return [{"code": code, "name": stocks[code]} for code in sorted(stocks)]

    def fetch_stock_kline(
        self,
        code: str,
        start_date: str = "",
        end_date: str = "",
        adjust: str = "qfq",
        include_turnover: bool = False,
    ) -> pd.DataFrame:
        """获取日 K 线，支持复权与内置换手率计算。"""
        symbol = normalize_code(code)
        normalized_end = end_date.strip().replace("-", "")
        kwargs: dict[str, Any] = {}
        if normalized_start := start_date.strip().replace("-", ""):
            kwargs["since"] = normalized_start
        frame = self._call(
            "bars_all",
            symbol.raw,
            frequency=_DAILY_FREQUENCY,
            adjust=adjust or None,
            turnover=include_turnover,
            **kwargs,
        )
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return pd.DataFrame(columns=_KLINE_COLUMNS)

        end_boundary = None
        if normalized_end:
            parsed_end = pd.to_datetime(normalized_end, format="%Y%m%d", errors="coerce")
            if pd.notna(parsed_end):
                end_boundary = parsed_end.date()
        date_column = "datetime" if "datetime" in frame.columns else frame.columns[0]
        rows: list[dict[str, Any]] = []
        for row in frame.to_dict("records"):
            parsed_date = pd.to_datetime(row.get(date_column), errors="coerce")
            if pd.isna(parsed_date):
                continue
            trading_date = parsed_date.date()
            if end_boundary is not None and trading_date > end_boundary:
                continue
            rows.append(
                {
                    "date": trading_date.strftime("%Y-%m-%d"),
                    "open": safe_float(row.get("open")),
                    "close": safe_float(row.get("close")),
                    "high": safe_float(row.get("high")),
                    "low": safe_float(row.get("low")),
                    "volume": safe_float(row.get("vol")),
                    "amount": safe_float(row.get("amount")),
                    "turnover_pct": safe_float(row.get("turnover")) if include_turnover else None,
                }
            )
        result = (
            pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume", "amount", "turnover_pct"])
            .dropna(subset=["open", "close", "high", "low"])
            .sort_values("date")
            .drop_duplicates(subset=["date"], keep="last")
            .reset_index(drop=True)
        )
        result["pre_close"] = result["close"].shift(1)
        return result[_KLINE_COLUMNS]

    def fetch_stock_quotes(self, codes: list[str]) -> dict[str, dict[str, Any]]:
        """批量获取标准化实时行情（沪深京）。

        沪深走 tdxhub 的 quotes()；北交所(market=2)被 tdxpy 客户端守卫
        拒绝，直接走协议命令。两者均按协议上限 80 条分块请求。
        """
        symbols = [normalize_code(code) for code in dict.fromkeys(codes)]
        if not symbols:
            return {}
        requested_codes = {symbol.raw for symbol in symbols}
        quotes: dict[str, dict[str, Any]] = {}
        quoted_at = datetime.now().isoformat(timespec="seconds")

        def collect(rows: Any) -> None:
            for row in rows or []:
                quote = _parse_quote_row(row, requested_codes, quoted_at)
                if quote is not None:
                    quotes.setdefault(quote["code"], quote)

        standard = [symbol for symbol in symbols if symbol.exchange.lower() != "bj"]
        beijing = [symbol for symbol in symbols if symbol.exchange.lower() == "bj"]
        for start in range(0, len(standard), _QUOTES_BATCH_SIZE):
            batch = standard[start : start + _QUOTES_BATCH_SIZE]
            frame = self._call("quotes", [symbol.prefixed_lower for symbol in batch])
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                collect(frame.to_dict("records"))
        for start in range(0, len(beijing), _QUOTES_BATCH_SIZE):
            batch = beijing[start : start + _QUOTES_BATCH_SIZE]
            collect(self._quotes.security_quotes_raw([(MARKET_BJ, symbol.raw) for symbol in batch]))
        return quotes

    def fetch_stock_quote(self, code: str) -> dict[str, Any]:
        """获取单只股票的标准化实时行情。"""
        normalized = normalize_code(code).raw
        return self.fetch_stock_quotes([normalized]).get(normalized, {})

    def fetch_finance_info(self, code: str) -> dict[str, Any]:
        """获取上市日期及股本等基础财务字段。"""
        symbol = normalize_code(code)
        frame = self._directory_frame(self._call("finance", symbol.raw))
        if frame is None:
            raise TdxhubUnavailableError(f"TDX 财务信息不可用: code={symbol.raw}")
        row = frame.iloc[0]
        return {
            "list_date": _date_number(row.get("ipo_date")),
            "updated_date": _date_number(row.get("updated_date")),
            "total_shares": safe_float(row.get("zongguben")),
            "float_shares": safe_float(row.get("liutongguben")),
        }


def _parse_quote_row(
    row: Any,
    requested_codes: set[str],
    quoted_at: str,
) -> dict[str, Any] | None:
    raw_code = safe_string(row.get("code"))
    if raw_code is None:
        return None
    code = raw_code.zfill(6)
    if code not in requested_codes:
        return None
    price = safe_float(row.get("price"))
    last_close = safe_float(row.get("last_close"))
    high = safe_float(row.get("high"))
    low = safe_float(row.get("low"))
    return {
        "code": code,
        "price": price,
        "last_close": last_close,
        "open": safe_float(row.get("open")),
        "high": high,
        "low": low,
        "change_amt": (round(price - last_close, 3) if price is not None and last_close is not None else None),
        "change_pct": (
            (price - last_close) / last_close * 100 if price is not None and last_close not in (None, 0) else None
        ),
        "amplitude_pct": (
            (high - low) / last_close * 100
            if high is not None and low is not None and last_close not in (None, 0)
            else None
        ),
        "volume": safe_float(row.get("vol")),
        "amount": safe_float(row.get("amount")),
        # 协议仅含时刻无日期，统一取抓取时刻，与原 tdx-api 行为一致
        "quoted_at": quoted_at,
    }


def _date_number(value: Any) -> str | None:
    number = safe_float(value)
    if number is None or number <= 0:
        return None
    return f"{int(number):08d}"


tdxhub_provider = TdxhubDataProvider()
