"""通过 tdxhub-sdk 进程内直连通达信行情与财务数据。

替代原 mootdx 直连与 tdx-api HTTP sidecar 两条链路：
底层统一走共享的 tdxhub StdQuotes 客户端。
"""

import logging
import math
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

import pandas as pd
from tdxhub.exceptions import TdxhubConnectionError, TdxhubIncompleteDataError
from tdxhub.quotes import Quotes
from tdxhub.tdx.deadline import remaining, request_budget

from app.configuration import get_settings
from app.core.cache import TTLCache
from app.core.market import (
    normalize_code,
    normalize_index_code,
    normalize_index_symbol,
    safe_float,
    safe_string,
)

logger = logging.getLogger(__name__)

_DAILY_FREQUENCY = 9
# TDX 协议单次行情快照的代码数量上限
_QUOTES_BATCH_SIZE = 80
_FUND_FLOW_DAYS = 60
# Store only fully validated historical daily aggregates, not the connection.
# Versioned keys keep these values separate from all other provider/SDK caches.
_fund_flow_day_cache = TTLCache(maxsize=6000, name="tdxhub_fund_flow_days")
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


class _FundFlowBatch(TypedDict):
    dates: list[str]
    items: list[dict[str, Any]]


class TdxhubError(RuntimeError):
    pass


class TdxhubUnavailableError(TdxhubError, ConnectionError):
    pass


_RECONNECT_ERRORS = (TdxhubConnectionError, ConnectionError, OSError, TimeoutError)


class SharedTdxhubQuotes:
    """进程内共享的 tdxhub 行情客户端。

    TDX 底层 TCP 客户端非线程安全，所有调用经统一锁串行化（上游
    tdx_semaphore 已将并发限制为 2，串行化与原 tdx-api 池大小 1 相当）。

    客户端重建是昂贵操作：SDK 构造函数会并发探测 ``SERVER.HQ`` 里的全部候选
    行情服务器且没有短路（``tdxhub.quotes._probe_quote_endpoints``），上游不可用
    时单次重建可达数十秒。若放任每个失败请求都各自重建，故障期间会形成"探测风暴"：
    N 个并发失败各自付出一次全量探测。这里做两件事收敛它：

    1. 重建走 single-flight（``_rebuild_lock``）：同一时刻只有一次探测在跑，
       排队的调用等待后直接复用重建结果，而不是各自重探；
    2. 重建失败进入冷却窗口：窗口内直接快速失败并让调用方降级到下一个 provider，
       而不是继续排队等待下一次昂贵的探测。

    注意仍需等待 single-flight 的调用方是等"一次"探测而非"自己的"探测，且这一次
    探测不占用 ``_lock``；``reset()`` / ``is_cooling_down()`` 等运维入口不会被探测
    阻塞。

    冷却只缓存**时间窗**、不缓存失效 IP 黑名单：冷却到期后的下一次请求会重新
    全量探测，届时恢复的服务器自然重新参与竞争，因此不存在"IP 被移除后挪不回来"。
    """

    def __init__(self, settings_provider: Callable[[], Any] = get_settings):
        self._settings_provider = settings_provider
        self._lock = threading.Lock()
        self._rebuild_lock = threading.Lock()
        self._client = None
        self._blocked_until = 0.0

    def _new_client(self):
        timeout = float(self._settings_provider().tdxhub_timeout_seconds)
        return Quotes.factory(market="std", timeout=timeout)

    def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        def invoke(client):
            return getattr(client, method)(*args, **kwargs)

        return self._invoke_with_retry(invoke)

    def is_cooling_down(self) -> bool:
        """当前是否处于重建冷却期。"""
        return time.monotonic() < self._blocked_until

    def cooldown_remaining_seconds(self) -> float:
        """距离冷却结束的剩余秒数。"""
        return max(0.0, self._blocked_until - time.monotonic())

    def _reject_if_cooling_down(self) -> None:
        if self.is_cooling_down():
            raise TdxhubUnavailableError(
                f"TDX 行情服务器处于重建冷却期，剩余 {self.cooldown_remaining_seconds():.1f}s"
            )

    def _invoke_with_retry(self, invoke: Callable[[Any], Any]) -> Any:
        self._reject_if_cooling_down()
        with self._lock:
            client = self._client
            if client is not None:
                try:
                    return invoke(client)
                except _RECONNECT_ERRORS as exc:
                    logger.warning("tdxhub 连接异常，重建客户端后重试: %s", exc)
                    self._client = None
        # 重建在串行锁之外：SDK 构造时的全量服务器探测可能耗时数十秒，持锁探测会
        # 让 reset()/is_cooling_down() 等入口一并阻塞。并发调用在这里排队，
        # 由 single-flight 保证只有一次探测，其余人复用重建结果。
        return invoke(self._rebuild())

    def _rebuild(self):
        with self._rebuild_lock:
            if self._client is not None:
                # 并发失败时，其它线程已完成重建，直接复用。
                return self._client
            # 排队等待 single-flight 期间，前一个线程可能已探测失败并进入冷却。
            # 此处复查才能保证"一轮故障只做一次全量探测"；只在调用入口检查会漏掉
            # 这个窗口，导致后续线程逐个重复付出探测代价。
            self._reject_if_cooling_down()
            try:
                client = self._acquire_client()
            except Exception:
                self._enter_cooldown()
                raise
            with self._lock:
                self._client = client
            return client

    def _cooldown_seconds(self) -> float:
        settings = self._settings_provider()
        return max(
            0.0,
            float(getattr(settings, "tdxhub_rebuild_cooldown_seconds", 30.0)),
        )

    def _enter_cooldown(self) -> None:
        self._blocked_until = time.monotonic() + self._cooldown_seconds()

    def _acquire_client(self):
        try:
            return self._new_client()
        except _RECONNECT_ERRORS as exc:
            raise TdxhubUnavailableError("TDX 行情服务器连接不可用") from exc

    def reset(self) -> None:
        """丢弃当前客户端，下次调用时重建，供异常恢复与测试隔离使用。"""
        with self._lock:
            self._client = None

    def clear_cooldown(self) -> None:
        """提前结束重建冷却，供后台测速任务主动尝试恢复链路。"""
        self._blocked_until = 0.0


shared_tdxhub_quotes = SharedTdxhubQuotes()


class TdxhubDataProvider:
    """通达信数据适配器：股票名称、K线、指数K线、实时行情、F10与财务基础信息。"""

    name = "tdxhub"
    DAILY_FREQUENCY = _DAILY_FREQUENCY
    DEFAULT_OFFSET = 10
    INDEX_KLINE_COLUMNS = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "pre_close",
        "change_pct",
    ]
    KLINE_COLUMNS = INDEX_KLINE_COLUMNS
    NUMERIC_COLUMNS = ["open", "close", "high", "low", "volume", "amount"]
    F10_CATEGORIES = (
        "最新提示",
        "公司概况",
        "财务分析",
        "股东研究",
        "股本结构",
        "资本运作",
        "业内点评",
        "行业分析",
        "公司大事",
    )

    def __init__(self, quotes: SharedTdxhubQuotes | None = None):
        self._quotes = quotes or shared_tdxhub_quotes

    def reset_client(self) -> None:
        """清空共享 tdxhub 客户端，便于异常恢复或测试隔离。"""
        self._quotes.reset()

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return self._quotes.call(method, *args, **kwargs)

    @staticmethod
    def _directory_frame(frame: Any) -> pd.DataFrame | None:
        return frame if isinstance(frame, pd.DataFrame) and not frame.empty else None

    def fetch_stock_fund_flow_history(
        self, code: str, *, dates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """兼容完整查询，或只查询调用方已固定的交易日期（用于后续批次）。"""
        return self._fetch_stock_fund_flow(code, dates=dates)["items"]

    def fetch_stock_fund_flow_page(self, code: str) -> _FundFlowBatch:
        """固定最近 60 日日期清单，但首次只聚合最新 20 日分笔。"""
        return self._fetch_stock_fund_flow(code, limit=20)

    def _fetch_stock_fund_flow(
        self, code: str, *, dates: list[str] | None = None, limit: int = 60,
    ) -> _FundFlowBatch:
        symbol = normalize_code(code).prefixed_lower
        settings = get_settings()
        budget = settings.tdxhub_fund_flow_timeout_seconds
        started_at = time.monotonic()
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        if dates is not None:
            # Never let a cursor supply unvalidated, duplicate or future dates.
            if not dates or len(dates) > _FUND_FLOW_DAYS:
                raise ValueError("tdxhub 资金流批次日期数量无效")
            dates = _fund_flow_dates(pd.DataFrame({"date": dates}), today)
        stage = "connect"
        current_date = "-"
        result: list[dict[str, Any]] = []
        cached_days = 0
        try:
            # Propagate the wall-clock budget through the SDK to each TCP read;
            # timing out asyncio.to_thread alone does not stop a worker thread.
            with request_budget(budget):
                with Quotes.factory(
                    market="std", timeout=settings.tdxhub_timeout_seconds, raise_exception=True,
                ) as client:
                    if dates is None:
                        stage = "daily_bars"
                        bars = client.bars(symbol, frequency=9, start=0, offset=_FUND_FLOW_DAYS)
                        dates = _fund_flow_dates(bars, today)
                    for current_date in dates[:limit]:
                        remaining()
                        cache_key = f"v1:{symbol}:{current_date}"
                        cached = _fund_flow_day_cache.get(cache_key) if current_date < today else None
                        if cached is not None:
                            result.append(dict(cached))
                            cached_days += 1
                            continue
                        stage = "historical_ticks"
                        flow = client.capital_flow(symbol, date=current_date.replace("-", ""))
                        remaining()
                        row = _parse_daily_fund_flow(current_date, flow)
                        result.append(row)
                        if current_date < today:
                            _fund_flow_day_cache.set(cache_key, dict(row), ttl=24 * 60 * 60)
            logger.info(
                "tdxhub 资金流查询完成: code=%s days=%s cached_days=%s elapsed=%.2fs",
                symbol, len(result), cached_days, time.monotonic() - started_at,
            )
            return {"dates": dates, "items": result}
        except Exception as error:
            elapsed = time.monotonic() - started_at
            logger.warning(
                "tdxhub 资金流查询失败: code=%s stage=%s date=%s completed_days=%s "
                "cached_days=%s elapsed=%.2fs budget=%ss error_type=%s",
                symbol, stage, current_date, len(result), cached_days, elapsed, budget, type(error).__name__,
            )
            context = f"阶段 {stage}，日期 {current_date}，已完成 {len(result)} 日"
            # Old SDK defaults turn exhausted request deadlines into None and
            # then a generic paging connection error. Preserve the true category.
            if elapsed >= budget:
                raise TimeoutError(f"tdxhub 资金流总查询时限 {budget:g} 秒已耗尽（{context}）") from error
            if isinstance(error, TimeoutError):
                raise TimeoutError(f"tdxhub 资金流请求超时（{context}）") from error
            if isinstance(error, TdxhubIncompleteDataError):
                raise
            raise TdxhubConnectionError(f"tdxhub 资金流查询失败（{context}）") from error

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
                    # tdxhub bars_all 的 vol 单位为手；统一历史日线契约使用股。
                    "volume": (
                        value * 100 if (value := safe_float(row.get("vol"))) is not None else None
                    ),
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

        统一走 SDK 0.3.0 的 quotes()，由 SDK 负责去重、80 条分块及
        北交所原生协议路由，避免某批失败后返回看似完整的部分快照。
        """
        symbols = [normalize_code(code) for code in dict.fromkeys(codes)]
        if not symbols:
            return {}
        requested_codes = {symbol.raw for symbol in symbols}
        frame = self._call("quotes", [symbol.prefixed_lower for symbol in symbols], batch_size=_QUOTES_BATCH_SIZE)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return {}
        quotes: dict[str, dict[str, Any]] = {}
        quoted_at = datetime.now().isoformat(timespec="seconds")
        for row in frame.to_dict("records"):
            quote = _parse_quote_row(row, requested_codes, quoted_at)
            if quote is not None:
                quotes.setdefault(quote["code"], quote)
        return quotes

    def fetch_stock_quote(self, code: str) -> dict[str, Any]:
        """获取单只股票的标准化实时行情。"""
        normalized = normalize_code(code).raw
        return self.fetch_stock_quotes([normalized]).get(normalized, {})

    def fetch_stock_xdxr(self, code: str) -> pd.DataFrame:
        """获取 A 股除权除息、送配股及扩缩股事件。"""
        symbol = normalize_code(code)
        frame = self._call("xdxr", symbol.raw)
        if not isinstance(frame, pd.DataFrame):
            raise TdxhubUnavailableError(f"TDX XDXR 响应格式无效: code={symbol.raw}")
        return frame.copy()

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

    def fetch_basic_info(self, code: str) -> dict[str, str]:
        """通过通达信 F10 接口获取个股各类基本信息。

        Param:
            code: 6 位股票代码
        Return:
            dict[str, str]: F10 分类名称到文本内容的映射
        """
        sym = normalize_code(code)
        result: dict[str, str] = {}
        for category in self.F10_CATEGORIES:
            frame = self._quotes.call("F10", symbol=sym.raw, name=category)
            content = ""
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                content = str(frame.iloc[0].get("content") or "")
            result[category] = content
        return result

    def fetch_index_kline(self, symbol: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """通过通达信本地接口获取指数 K 线并衍生昨收与涨跌幅。

        Param:
            symbol: 指数代码，支持 000001、sh000001 等格式
            start_date: 起始日期，格式 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期，格式 YYYYMMDD 或 YYYY-MM-DD
        Return:
            包含 date、OHLCV、amount、pre_close、change_pct 的 DataFrame
        """
        raw_symbol = self._normalize_index_request(symbol)
        offset = self._calculate_offset(start_date, end_date)
        raw_df = self._quotes.call(
            "index",
            symbol=raw_symbol,
            frequency=self.DAILY_FREQUENCY,
            start=0,
            offset=offset,
        )
        # 指数与个股的原始 vol 量纲不同：个股 bars_all 的 vol 是「手」，而指数
        # bars 的 vol 是「万手」。都要统一到「股」，因此这里的系数是个股路径的
        # 100 倍。系数用错会让指数成交量与成交额不自洽（amount/volume 偏离
        # 成分股均价三个数量级），并与腾讯指数链相差 100 倍。
        return self._format_index_kline_df(
            raw_df, start_date=start_date, end_date=end_date, volume_multiplier=10_000,
        )

    def fetch_stock_bars(self, code: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """通过通达信底层原始 bars 接口获取个股 K 线（轻量直接查询）。

        Param:
            code: 6 位股票代码
            start_date: 起始日期，格式 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期，格式 YYYYMMDD 或 YYYY-MM-DD
        Return:
            包含 date、OHLCV、amount、pre_close、change_pct 的 DataFrame
        """
        sym = normalize_code(code)
        offset = self._calculate_offset(start_date, end_date)
        raw_df = self._quotes.call(
            "bars",
            symbol=sym.raw,
            frequency=self.DAILY_FREQUENCY,
            start=0,
            offset=offset,
        )
        return self._format_index_kline_df(raw_df, start_date=start_date, end_date=end_date)

    def _calculate_offset(self, start_date: str = "", end_date: str = "") -> int:
        """根据日期范围计算 TDX 请求条数，默认返回最近 DEFAULT_OFFSET 条。"""
        start_dt = self._parse_date(start_date)
        end_dt = self._parse_date(end_date)
        if not start_dt or not end_dt:
            return self.DEFAULT_OFFSET
        if end_dt < start_dt:
            raise ValueError(f"结束日期早于起始日期: start_date={start_date}, end_date={end_date}")
        return max((end_dt - start_dt).days + 1, 1)

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        """解析 YYYYMMDD 或 YYYY-MM-DD 日期；空值返回 None。"""
        if not value:
            return None
        normalized = str(value).strip().replace("-", "")
        return datetime.strptime(normalized, "%Y%m%d")

    @staticmethod
    def _normalize_index_request(symbol: str) -> str:
        """归一化 TDX 指数代码；市场由 tdxhub 按代码段自动推断。"""
        normalized_symbol = normalize_index_symbol(symbol.strip().lower())
        raw_symbol = str(normalize_index_code(normalized_symbol))
        if not raw_symbol.isdigit() or len(raw_symbol) != 6:
            raise ValueError(f"无效指数代码: {symbol}，需要6位数字")
        return raw_symbol

    def _format_index_kline_df(
        self,
        raw_df: pd.DataFrame | None,
        *,
        start_date: str = "",
        end_date: str = "",
        volume_multiplier: int | float = 1,
    ) -> pd.DataFrame:
        """将 tdxhub 原始 K 线 DataFrame 统一整理为标准列。"""
        if raw_df is None or not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
            return pd.DataFrame(columns=self.INDEX_KLINE_COLUMNS)

        df = self._ensure_datetime_column(raw_df)
        required_columns = ["datetime", *self.NUMERIC_COLUMNS]
        missing = [column for column in required_columns if column not in df.columns]
        if missing:
            logger.warning("TDX K线字段缺失: missing=%s", missing)
            return pd.DataFrame(columns=self.INDEX_KLINE_COLUMNS)

        result = df[required_columns].copy()
        result["date"] = pd.to_datetime(result["datetime"], errors="coerce")
        for column in self.NUMERIC_COLUMNS:
            result[column] = pd.to_numeric(result[column], errors="coerce")

        result = result.dropna(subset=["date"]).sort_values("date")
        result = result.drop_duplicates(subset=["date"], keep="last")
        if volume_multiplier != 1:
            result["volume"] = result["volume"] * volume_multiplier

        result["pre_close"] = result["close"].shift(1)
        result["change_pct"] = (result["close"] - result["pre_close"]) / result["pre_close"] * 100

        result = self._filter_by_date_range(result, start_date=start_date, end_date=end_date)
        result["date"] = result["date"].dt.strftime("%Y-%m-%d")
        return result[self.INDEX_KLINE_COLUMNS].reset_index(drop=True)

    @staticmethod
    def _ensure_datetime_column(raw_df: pd.DataFrame) -> pd.DataFrame:
        """兼容 tdxhub 将 datetime 放在列或索引上的两种返回形态。"""
        df = raw_df.copy()
        if "datetime" in df.columns:
            return df.reset_index(drop=True)

        index_name = df.index.name or "datetime"
        df = df.reset_index()
        if "datetime" not in df.columns and index_name in df.columns:
            df = df.rename(columns={index_name: "datetime"})
        return df

    def _filter_by_date_range(self, df: pd.DataFrame, *, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """按日期范围过滤 K 线，保留过滤前算出的 pre_close。"""
        start_dt = self._parse_date(start_date)
        end_dt = self._parse_date(end_date)
        if start_dt is not None:
            df = df[df["date"] >= start_dt]
        if end_dt is not None:
            # 日 K 线可能带 15:00 时间，结束日期应包含当天完整交易数据。
            df = df[df["date"] < end_dt + timedelta(days=1)]
        return df.copy()


def _fund_flow_dates(bars: Any, today: str) -> list[str]:
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        raise TdxhubIncompleteDataError("tdxhub 资金流缺少有效日 K")
    if "datetime" in bars.columns:
        dates = pd.to_datetime(bars["datetime"], errors="coerce")
    elif "date" in bars.columns:
        dates = pd.to_datetime(bars["date"], errors="coerce")
    elif isinstance(bars.index, pd.DatetimeIndex):
        dates = pd.Series(bars.index)
    else:
        raise TdxhubIncompleteDataError("tdxhub 资金流日 K 缺少日期")
    if dates.isna().any():
        raise TdxhubIncompleteDataError("tdxhub 资金流日 K 日期无效")
    day_keys = dates.dt.strftime("%Y-%m-%d").tolist()
    if len(day_keys) != len(set(day_keys)) or any(day > today for day in day_keys):
        raise TdxhubIncompleteDataError("tdxhub 资金流日 K 日期重复或晚于当前交易日")
    return sorted(day_keys, reverse=True)[:_FUND_FLOW_DAYS]


def _parse_daily_fund_flow(day: str, flow: Any) -> dict[str, Any]:
    tiers = {"super_net": "超大单", "large_net": "大单", "medium_net": "中单", "small_net": "小单"}
    if not isinstance(flow, pd.DataFrame) or flow.empty or "net_amount" not in flow.columns:
        raise TdxhubIncompleteDataError(f"tdxhub {day} 缺少完整分笔资金流")
    count = safe_float(flow.attrs.get("trade_count"))
    if count is None or not math.isfinite(count) or count <= 0 or not flow.index.is_unique:
        raise TdxhubIncompleteDataError(f"tdxhub {day} 无有效成交分笔")
    if not set(tiers.values()).issubset(flow.index):
        raise TdxhubIncompleteDataError(f"tdxhub {day} 缺少资金分档")
    row = {"date": day, "main_net": flow.attrs.get("main_net")}
    row.update({key: flow.loc[tier, "net_amount"] for key, tier in tiers.items()})
    try:
        return _parse_fund_flow_history(pd.DataFrame([row]))[0]
    except ValueError as error:
        raise TdxhubIncompleteDataError(f"tdxhub {day} 资金流数值无效") from error


def _parse_fund_flow_history(frame: Any) -> list[dict[str, Any]]:
    """TDX 金额已为元；只重命名中单字段，不缩放、不补零、不交付残缺记录。"""
    fields = {
        "main_net": "main_net",
        "super_net": "super_net",
        "large_net": "large_net",
        "mid_net": "medium_net",
        "small_net": "small_net",
    }
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("tdxhub 个股历史资金流为空")
    if not {"date", *fields.values()}.issubset(frame.columns):
        raise ValueError("tdxhub 个股历史资金流缺少必要字段")
    result: list[dict[str, Any]] = []
    dates: set[str] = set()
    for record in frame.to_dict("records"):
        raw_date = safe_string(record["date"])
        if raw_date is None:
            raise ValueError("tdxhub 个股历史资金流日期缺失")
        try:
            date_key = datetime.strptime(raw_date, "%Y-%m-%d").date().isoformat()
        except ValueError as error:
            raise ValueError("tdxhub 个股历史资金流日期无效") from error
        if date_key in dates:
            raise ValueError("tdxhub 个股历史资金流日期重复")
        dates.add(date_key)
        item: dict[str, Any] = {"date": date_key}
        for target, source in fields.items():
            raw = record[source]
            value = safe_float(raw)
            if isinstance(raw, bool) or value is None or not math.isfinite(value):
                raise ValueError(f"tdxhub 个股历史资金流数值无效: field={source}")
            item[target] = value
        result.append(item)
    result.sort(key=lambda item: item["date"], reverse=True)
    return result[:60]


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
