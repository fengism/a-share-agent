import json
import logging
import math
import re
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import time as datetime_time
from threading import Lock
from typing import cast

import pandas as pd
import requests

from app.configuration import get_settings
from app.constants.http import SINA_FINANCE_HEADERS
from app.constants.market import (
    SINA_CN_RANK_URL,
    SINA_INDEX_INTRADAY_URL,
    SINA_INDEX_QUOTE_URL,
    SINA_MARKET_HQ_COUNT_URL,
    SINA_MARKET_HQ_URL,
    SINA_STOCK_KLINE_URL,
)
from app.core.cache import dated_cache_key
from app.core.cache import reference_cache as cache
from app.core.cache_policies import SINA_SPOT_SNAPSHOT, SINA_STOCK_NAMES
from app.core.concurrency.singleflight import SyncSingleFlight
from app.core.dataframes import coerce_numeric_columns, normalize_intraday_df, rename_and_keep_columns, rename_columns
from app.core.market import normalize_code, normalize_index_symbol, normalize_stock_name, safe_float
from app.infrastructure.providers.sina import bulletins as sina_bulletins
from app.infrastructure.providers.sina import financials as sina_financials
from app.infrastructure.providers.sina import futures as sina_futures
from app.infrastructure.providers.sina import industry as sina_industry
from app.infrastructure.providers.sina import reports as sina_reports
from app.infrastructure.providers.sina.parsing import parse_jsonp
from app.infrastructure.providers.sina.quotes import get_last_trade_date

logger = logging.getLogger(__name__)

_SINA_FACTOR_PATTERN = re.compile(r"^[^=]*=\s*", re.DOTALL)


class SinaSnapshotIncompleteError(RuntimeError):
    """新浪全市场分页未完整结束，禁止返回或缓存部分快照。"""


_sina_snapshot_health_lock = Lock()
_sina_snapshot_health: dict[str, object] = {
    "status": "unknown",
    "updated_at": None,
    "rows": 0,
    "expected_count": 0,
    "pages": 0,
    "duration_ms": 0.0,
    "page_ms_avg": 0.0,
    "page_ms_max": 0.0,
    "error_type": None,
    "error_message": None,
}


def _update_sina_snapshot_health(**updates: object) -> None:
    with _sina_snapshot_health_lock:
        _sina_snapshot_health.update(updates)
        _sina_snapshot_health["updated_at"] = datetime.now().isoformat(timespec="seconds")


def sina_snapshot_health_snapshot() -> dict[str, object]:
    with _sina_snapshot_health_lock:
        return dict(_sina_snapshot_health)


def _parse_adjustment_factor_payload(text: str, method: str) -> pd.DataFrame:
    match = _SINA_FACTOR_PATTERN.match(text.strip())
    if not match:
        raise ValueError(f"新浪 {method} 复权因子响应格式无效")
    try:
        payload, _ = json.JSONDecoder().raw_decode(text.strip()[match.end():].lstrip())
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError(f"新浪 {method} 复权因子响应格式无效") from error
    if not isinstance(payload, dict):
        raise ValueError(f"新浪 {method} 复权因子响应格式无效")
    rows = payload.get("data", [])
    if not rows:
        raise ValueError(f"新浪 {method} 复权因子不可用")
    frame = pd.DataFrame(rows)
    if {"d", "f"}.issubset(frame.columns):
        frame = frame.rename(columns={"d": "date", "f": "factor"})
    elif len(frame.columns) >= 2:
        frame = frame.iloc[:, :2].copy()
        frame.columns = ["date", "factor"]
    else:
        raise ValueError(f"新浪 {method} 复权因子字段无效")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["factor"] = pd.to_numeric(frame["factor"], errors="raise")
    finite_positive = frame["factor"].map(lambda value: math.isfinite(float(value)) and value > 0)
    if not finite_positive.all():
        raise ValueError(f"新浪 {method} 复权因子包含非正或非有限值")
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    if frame.empty:
        raise ValueError(f"新浪 {method} 复权因子无有效值")
    return frame.reset_index(drop=True)


class SinaDataProvider:
    """Purpose: 直接对接新浪财经接口的 K线、指数、快照、分时等数据提供器（备用源）。"""

    fetch_crude_oil_quotes = staticmethod(sina_futures.fetch_crude_oil_quotes)
    fetch_futures_quotes = staticmethod(sina_futures.fetch_futures_quotes)
    fetch_futures_history = staticmethod(sina_futures.fetch_futures_history)
    fetch_last_trade_date = staticmethod(get_last_trade_date)

    HQ_PAGE_SIZE = 100
    HQ_MAX_PAGES = 80
    HQ_PAGE_MAX_ATTEMPTS = 3
    HQ_PAGE_WORKERS = 4
    HQ_RETRY_DELAY_SECONDS = 0.3
    HQ_MIN_RECORDS = 4_000
    RANK_PAGE_SIZE = 30
    RANK_BATCH_SIZE = 8
    RANK_WORKERS = 8
    RANK_MAX_PAGES = 200
    RANK_MIN_RECORDS = 4000
    NAMES_CACHE_TTL = SINA_STOCK_NAMES.ttl_seconds
    SNAPSHOT_CACHE_TTL = SINA_SPOT_SNAPSHOT.ttl_seconds
    name = "sina"

    def __init__(self):
        """初始化独立的新浪请求会话。"""
        # Sina 接口常常无法通过代理访问，使用独立 session 并禁用代理
        self._session = requests.Session()
        self._session.trust_env = False
        self._hq_singleflight = SyncSingleFlight[list[dict]]()

    def fetch_kline(self, code: str, period: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """新浪股票 K 线（自行处理 JSONP/范围截取与列重命名）。
        Param:
            code: 6 位股票代码
            period: daily/weekly/monthly
            start_date: 起始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
        Return:
            包含日期与 OHLCV 等列的 DataFrame
        """
        sym = normalize_code(code)
        symbol = sym.prefixed_lower
        scale_map = {"daily": "240", "weekly": "1200", "monthly": "5200"}
        scale = scale_map.get(period, "240")

        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d")
            delta_days = (datetime.now() - start_dt).days
            if period == "daily":
                datalen = max(delta_days * 5 // 7 + 20, 30)
            elif period == "weekly":
                datalen = max(delta_days // 7 + 5, 10)
            else:
                datalen = max(delta_days // 30 + 3, 5)
            datalen = min(datalen, 2000)
        except Exception as e:
            logger.warning("解析日期范围失败: %s", e)
            datalen = 500
        params = {
            "symbol": symbol,
            "scale": scale,
            "ma": "no",
            "datalen": str(datalen),
        }
        r = self._session.get(SINA_STOCK_KLINE_URL, params=params, headers=SINA_FINANCE_HEADERS, timeout=10)
        text = r.text.strip()
        if text.startswith("=") or text.startswith("/*"):
            m = re.search(r"\[.*\]", text)
            if not m:
                return pd.DataFrame()
            records = json.loads(m.group(0))
        else:
            records = json.loads(text)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        # CN_MarketDataService.getKLineData 的 volume 原始单位为股；历史回填库也统一存股。
        # 这里不能除以 100，否则该无成交额 fallback 无法在回填层自动识别并恢复单位。
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df = rename_columns(
            df,
            {"day": "日期", "open": "开盘", "high": "最高", "low": "最低", "close": "收盘", "volume": "成交量"},
        )
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        start_dt = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
        end_dt = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
        df = df[df["日期"].notna()]
        if pd.notna(start_dt):
            df = df[df["日期"] >= start_dt]
        if pd.notna(end_dt):
            df = df[df["日期"] <= end_dt]
        df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")
        return df

    def fetch_adjustment_factors(self, code: str) -> dict[str, pd.DataFrame]:
        """获取新浪 qfq/hfq 除权日乘法因子；不等同于 TDX 仿射公司行为。"""
        symbol = normalize_code(code).prefixed_lower
        result: dict[str, pd.DataFrame] = {}
        for method in ("qfq", "hfq"):
            response = self._session.get(
                f"https://finance.sina.com.cn/realstock/company/{symbol}/{method}.js",
                headers=SINA_FINANCE_HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            result[method] = _parse_adjustment_factor_payload(response.text, method)
        return result

    def fetch_index_intraday(self, symbol: str) -> pd.DataFrame:
        """Fetch and normalize the current-session minute line for a market index."""
        response = self._session.get(
            SINA_INDEX_INTRADAY_URL,
            params={
                "symbol": normalize_index_symbol(symbol.strip().lower()),
                "version": "7.11.0",
                "dpc": "1",
            },
            headers=SINA_FINANCE_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") if isinstance(payload, Mapping) else None
        status = result.get("status") if isinstance(result, Mapping) else None
        rows = result.get("data") if isinstance(result, Mapping) else None
        if not isinstance(status, Mapping) or status.get("code") != 0 or not isinstance(rows, list):
            raise RuntimeError("新浪指数分时接口返回错误")

        normalized_by_time: dict[str, dict[str, float | str | None]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            time_text = str(row.get("m") or "").strip()
            if re.fullmatch(r"\d{2}:\d{2}:\d{2}", time_text) is None:
                continue
            price = safe_float(row.get("p"))
            if price is None or price <= 0:
                continue
            normalized_by_time[time_text] = {
                "time": time_text,
                "price": price,
                "avg_price": safe_float(row.get("avg_p")),
                "volume": safe_float(row.get("v")),
                "total_volume": safe_float(row.get("tot_v")),
            }

        return pd.DataFrame(
            [normalized_by_time[key] for key in sorted(normalized_by_time)],
            columns=["time", "price", "avg_price", "volume", "total_volume"],
        )

    def fetch_market_indices(self) -> pd.DataFrame:
        """新浪沪深重要指数实时行情并合并为一张 DataFrame
        https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple?page=1&num=40&sort=symbol&asc=1&node=dpzs&_s_r_a=init
        Return:
            包含代码、名称、最新价、涨跌额、涨跌幅、成交量（手）、成交额（万元） 等列的 DataFrame
        """
        payload = {
            "page": "1",
            "num": "40",
            "sort": "symbol",
            "asc": "1",
            "node": "dpzs",
            "_s_r_a": "init",
        }
        big_df = pd.DataFrame()
        response = self._session.get(SINA_INDEX_QUOTE_URL, params=payload, timeout=10)
        response.raise_for_status()
        data_json = json.loads(response.text)
        if not data_json:
            return big_df
        big_df = pd.DataFrame(data_json)
        big_df = coerce_numeric_columns(
            big_df, ["trade", "pricechange", "changepercent", "buy", "sell", "settlement", "open", "high", "low"]
        )
        big_df.columns = [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "_",
            "_",
            "昨收",
            "今开",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "_",
            "_",
        ]
        big_df = big_df[
            ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "昨收", "今开", "最高", "最低", "成交量", "成交额"]
        ]
        return coerce_numeric_columns(
            big_df, ["最新价", "涨跌额", "涨跌幅", "昨收", "今开", "最高", "最低", "成交量", "成交额"]
        )

    @staticmethod
    def _is_cnrank_a_share_code(code: str) -> bool:
        return code.startswith(
            ("600", "601", "603", "605", "688", "689", "000", "001", "002", "003", "300", "301")
        ) or code.startswith(("4", "8", "920"))

    @staticmethod
    def _normalize_cnrank_rows(rows: list[dict]) -> pd.DataFrame:
        normalized_rows: list[dict] = []
        seen_codes: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            code = str(row.get("code") or "").strip()
            name = normalize_stock_name(str(row.get("name") or ""))
            if (
                len(code) != 6
                or not code.isdigit()
                or not SinaDataProvider._is_cnrank_a_share_code(code)
                or not name
                or code in seen_codes
            ):
                continue
            seen_codes.add(code)

            def number(field: str, scale: float = 1.0) -> float | None:
                value = safe_float(row.get(field))
                return value * scale if value is not None else None

            normalized_rows.append(
                {
                    "代码": code,
                    "名称": name,
                    "最新价": number("price"),
                    "涨跌幅": number("percent"),
                    "振幅": number("amplitude"),
                    "成交量": number("totalVolume"),
                    "成交额": number("totalAmount"),
                    "换手率": number("turnOver"),
                    "市盈率-动态": number("pe", 10_000),
                    "市净率": number("pb"),
                    "总市值": number("totalShare", 10_000),
                    "流通市值": number("cirValue", 10_000),
                }
            )
        return pd.DataFrame(normalized_rows)

    def _fetch_cnrank_page(self, page: int) -> list[dict]:
        try:
            response = self._session.get(
                SINA_CN_RANK_URL,
                params={
                    "sort": "percent",
                    "num": self.RANK_PAGE_SIZE,
                    "hnew": "1",
                    "hcnew": "1",
                    "asc": "0",
                    "node": "hs",
                    "page": page,
                },
                headers={**SINA_FINANCE_HEADERS, "Referer": "https://finance.sina.cn/"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            raise RuntimeError(f"新浪 cnrank 第 {page} 页请求失败: {error}") from error
        rows = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(payload, Mapping) or payload.get("code") != 0 or not isinstance(rows, list):
            raise RuntimeError(f"新浪 cnrank 第 {page} 页返回格式无效")
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    def fetch_stock_rank_snapshot(self) -> pd.DataFrame:
        first_page = self._fetch_cnrank_page(1)
        records = list(first_page)
        terminal = len(first_page) < self.RANK_PAGE_SIZE

        if not terminal:
            with ThreadPoolExecutor(
                max_workers=max(1, self.RANK_WORKERS),
                thread_name_prefix="sina-cnrank",
            ) as executor:
                for start_page in range(2, self.RANK_MAX_PAGES + 1, self.RANK_BATCH_SIZE):
                    page_numbers = list(
                        range(
                            start_page,
                            min(start_page + self.RANK_BATCH_SIZE, self.RANK_MAX_PAGES + 1),
                        )
                    )
                    futures = {page: executor.submit(self._fetch_cnrank_page, page) for page in page_numbers}
                    for page in page_numbers:
                        page_rows = futures[page].result()
                        records.extend(page_rows)
                        if len(page_rows) < self.RANK_PAGE_SIZE:
                            terminal = True
                            break
                    if terminal:
                        break

        if not terminal:
            raise RuntimeError(f"新浪 cnrank 未在 {self.RANK_MAX_PAGES} 页内结束")
        frame = self._normalize_cnrank_rows(records)
        if len(frame.index) < self.RANK_MIN_RECORDS:
            raise RuntimeError(f"新浪 cnrank A 股快照不足: {len(frame.index)} < {self.RANK_MIN_RECORDS}")
        return frame

    def fetch_revenue_breakdown(self, code: str) -> dict[str, object]:
        """获取新浪最新披露的营收与毛利构成。"""
        return cast(dict[str, object], sina_financials.fetch_revenue_breakdown(self._session, code))

    def fetch_stock_financials(
        self,
        code: str,
        indicator: str,
        *,
        num: int = 4,
    ) -> pd.DataFrame:
        """获取新浪资产负债表、利润表或现金流量表。"""
        return sina_financials.fetch_stock_financials(
            self._session,
            code,
            indicator,
            num=num,
        )

    def fetch_sw_industry_mappings(self) -> sina_industry.SwMappingMap:
        """获取申万一级、二级、三级分类及完整 A 股成分映射。"""
        return sina_industry.fetch_sw_industry_mappings(self._session)

    def fetch_stock_bulletins(self, code: str, page: int = 1, page_size: int = 10, notice_type: str = "") -> dict:
        """新浪个股公告列表（CB_AllService.getBulletinList）。

        Return:
            归一化字典：code、name、page、page_size、total_pages、items
        """
        return cast(
            dict,
            sina_bulletins.fetch_stock_bulletins(
                self._session,
                code,
                page=page,
                page_size=page_size,
                notice_type=notice_type,
            ),
        )

    def fetch_stock_reports(self, code: str, page: int = 1, page_size: int = 10) -> dict:
        """新浪个股研报评级列表（ReportService.getList）。

        Return:
            归一化字典：code、page、page_size、total_count、total_pages、items
        """
        sym = normalize_code(code)
        return cast(
            dict,
            sina_reports.fetch_stock_reports(
                self._session,
                sym.prefixed_lower,
                page=page,
                page_size=page_size,
            ),
        )

    def fetch_stock_names(self) -> list[dict]:
        """获取全市场 A 股的名称代码对照表（新浪行情列表分页拉取，按日缓存）。

        Return:
            [{"code": 股票代码, "name": 股票名称}, ...] 列表
        """
        records = self._fetch_market_hq_records(ttl=self.NAMES_CACHE_TTL, cache_scope="stock_names")
        return [
            {"code": str(item.get("code", "")), "name": str(item.get("name", "")).replace(" ", "")}
            for item in records
            if item.get("code") and item.get("name")
        ]

    @staticmethod
    def _spot_snapshot_ttl(now: datetime | None = None) -> int:
        """交易时段保持较短 TTL，休市后降低全市场重复抓取频率。"""
        current = now or datetime.now()
        is_live = (
            current.weekday() < 5
            and datetime_time(9, 0) <= current.time() <= datetime_time(15, 30)
        )
        return SINA_SPOT_SNAPSHOT.ttl_seconds if is_live else 30 * 60

    def fetch_spot_snapshot(self) -> pd.DataFrame:
        """获取全市场 A 股实时行情快照（新浪行情列表，60 秒内复用缓存）。

        Return:
            包含代码、名称、最新价、OHLCV、市盈率、市净率、换手率等的 DataFrame
        """
        records = self._fetch_market_hq_records(
            ttl=self._spot_snapshot_ttl(), cache_scope="spot_snapshot"
        )
        return self._records_to_snapshot_df(records)

    def _records_to_snapshot_df(self, records: list[dict]) -> pd.DataFrame:
        """将新浪行情原始记录转换为标准化的全市场快照 DataFrame。

        Param:
            records: 新浪 hq_records 列表
        Return:
            标准化快照 DataFrame；空记录返回空 DataFrame
        """
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = rename_and_keep_columns(
            df,
            {
                "code": "代码",
                "name": "名称",
                "trade": "最新价",
                "pricechange": "涨跌额",
                "changepercent": "涨跌幅",
                "buy": "买入",
                "sell": "卖出",
                "settlement": "昨收",
                "open": "今开",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "amount": "成交额",
                "per": "市盈率-动态",
                "pb": "市净率",
                "mktcap": "总市值",
                "nmc": "流通市值",
                "turnoverratio": "换手率",
                "ticktime": "时间",
            },
        )
        if "成交量" in df.columns:
            # Market_Center.getHQNodeData 的 volume 已按“股”返回。这里仅做数值化；
            # 不要套用东方财富等以“手”为单位的数据源所需的 ×100 转换。
            df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce")
        if "总市值" in df.columns:
            df["总市值"] = pd.to_numeric(df["总市值"], errors="coerce") * 10000
        if "流通市值" in df.columns:
            df["流通市值"] = pd.to_numeric(df["流通市值"], errors="coerce") * 10000
        codes = df.get("代码", pd.Series(dtype="object")).astype(str)
        price = pd.to_numeric(df.get("最新价"), errors="coerce")
        volume = pd.to_numeric(df.get("成交量"), errors="coerce")
        amount = pd.to_numeric(df.get("成交额"), errors="coerce")
        valid_ratio = (price > 0) & (volume > 0) & (amount > 0)
        ratios = (amount[valid_ratio] / (volume[valid_ratio] * price[valid_ratio])).dropna()
        quality = {
            "rows": len(df),
            "unique_codes": int(codes.nunique()),
            "duplicate_codes": int(codes.duplicated().sum()),
            "positive_prices": int((price > 0).sum()),
            "positive_volume": int((volume > 0).sum()),
            "positive_amount": int((amount > 0).sum()),
            "amount_volume_price_ratio_median": (
                round(float(ratios.median()), 6) if not ratios.empty else None
            ),
        }
        df.attrs["stock_spot_quality"] = quality
        logger.info("新浪全市场快照质量: %s", quality)
        return df

    def _fetch_market_hq_expected_count(self) -> int:
        last_error: Exception | None = None
        for attempt in range(1, self.HQ_PAGE_MAX_ATTEMPTS + 1):
            try:
                response = self._session.get(
                    SINA_MARKET_HQ_COUNT_URL,
                    params={"node": "hs_a"},
                    timeout=15,
                )
                response.raise_for_status()
                payload = response.json()
                expected = int(payload)
                if expected < self.HQ_MIN_RECORDS:
                    raise SinaSnapshotIncompleteError(
                        f"新浪全市场预期数量异常: expected={expected} minimum={self.HQ_MIN_RECORDS}"
                    )
                return expected
            except Exception as error:
                last_error = error
                if attempt < self.HQ_PAGE_MAX_ATTEMPTS:
                    time.sleep(self.HQ_RETRY_DELAY_SECONDS * attempt)
        raise SinaSnapshotIncompleteError("新浪全市场计数接口连续失败") from last_error

    def _fetch_market_hq_page(self, page: int) -> tuple[list[dict], float, int]:
        last_error: Exception | None = None
        for attempt in range(1, self.HQ_PAGE_MAX_ATTEMPTS + 1):
            page_started_at = time.perf_counter()
            try:
                response = self._session.get(
                    SINA_MARKET_HQ_URL,
                    params={
                        "page": page,
                        "num": self.HQ_PAGE_SIZE,
                        "sort": "symbol",
                        "asc": 1,
                        "node": "hs_a",
                        "_s_r_a": "init",
                    },
                    timeout=15,
                )
                response.raise_for_status()
                if not response.text.strip():
                    raise SinaSnapshotIncompleteError(f"新浪全市场快照第 {page} 页响应为空")
                payload = response.json()
                if not isinstance(payload, list):
                    raise SinaSnapshotIncompleteError(
                        f"新浪全市场快照第 {page} 页返回类型无效: {type(payload).__name__}"
                    )
                if not payload:
                    raise SinaSnapshotIncompleteError(f"新浪全市场快照第 {page} 页意外为空")
                if any(not isinstance(row, Mapping) for row in payload):
                    raise SinaSnapshotIncompleteError(f"新浪全市场快照第 {page} 页包含无效记录")
                latency_ms = round((time.perf_counter() - page_started_at) * 1000, 2)
                return [dict(row) for row in payload], latency_ms, attempt
            except Exception as error:
                last_error = error
                if attempt < self.HQ_PAGE_MAX_ATTEMPTS:
                    time.sleep(self.HQ_RETRY_DELAY_SECONDS * attempt)
        raise SinaSnapshotIncompleteError(
            f"新浪全市场快照第 {page} 页连续失败 {self.HQ_PAGE_MAX_ATTEMPTS} 次"
        ) from last_error

    def _load_market_hq_records(self, ttl: int | None = None, cache_scope: str = "default") -> list[dict]:
        """按官方总数并发拉取完整 A 股快照；任一页失败则整批失败且不缓存。"""
        cache_key: str | None = dated_cache_key("sina", "hq_records", cache_scope) if ttl else None
        if cache_key is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return cast(list[dict], cached)

        started_at = time.perf_counter()
        _update_sina_snapshot_health(
            status="fetching",
            error_type=None,
            error_message=None,
        )
        try:
            expected_count = self._fetch_market_hq_expected_count()
            total_pages = math.ceil(expected_count / self.HQ_PAGE_SIZE)
            if total_pages > self.HQ_MAX_PAGES:
                raise SinaSnapshotIncompleteError(
                    f"新浪全市场快照预期页数超过上限: pages={total_pages} max={self.HQ_MAX_PAGES}"
                )

            page_results: dict[int, tuple[list[dict], float, int]] = {}
            page_workers = max(
                1,
                min(get_settings().sina_hq_page_workers, self.HQ_PAGE_WORKERS, total_pages),
            )
            with ThreadPoolExecutor(
                max_workers=page_workers,
                thread_name_prefix="sina-market-hq",
            ) as executor:
                futures = {
                    page: executor.submit(self._fetch_market_hq_page, page)
                    for page in range(1, total_pages + 1)
                }
                for page in range(1, total_pages + 1):
                    page_results[page] = futures[page].result()

            records: list[dict] = []
            page_latencies: list[float] = []
            page_attempts: list[int] = []
            for page in range(1, total_pages + 1):
                page_records, latency_ms, attempts = page_results[page]
                expected_page_size = (
                    self.HQ_PAGE_SIZE
                    if page < total_pages
                    else expected_count - self.HQ_PAGE_SIZE * (total_pages - 1)
                )
                if len(page_records) != expected_page_size:
                    raise SinaSnapshotIncompleteError(
                        f"新浪全市场快照第 {page} 页数量异常: "
                        f"rows={len(page_records)} expected={expected_page_size}"
                    )
                records.extend(page_records)
                page_latencies.append(latency_ms)
                page_attempts.append(attempts)

            codes = [str(row.get("code") or "").strip() for row in records]
            valid_codes = [code for code in codes if len(code) == 6 and code.isdigit()]
            duplicate_count = len(valid_codes) - len(set(valid_codes))
            if len(records) != expected_count:
                raise SinaSnapshotIncompleteError(
                    f"新浪全市场快照数量与计数接口不一致: rows={len(records)} expected={expected_count}"
                )
            if len(valid_codes) != len(records):
                raise SinaSnapshotIncompleteError(
                    f"新浪全市场快照证券代码无效: rows={len(records)} valid_codes={len(valid_codes)}"
                )
            if duplicate_count:
                raise SinaSnapshotIncompleteError(
                    f"新浪全市场快照存在重复代码: duplicates={duplicate_count}"
                )

            if ttl:
                for scope, scope_ttl in (
                    (cache_scope, ttl),
                    ("stock_names", self.NAMES_CACHE_TTL),
                ):
                    cache.set(dated_cache_key("sina", "hq_records", scope), records, ttl=scope_ttl)
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            page_ms_avg = sum(page_latencies) / len(page_latencies) if page_latencies else 0.0
            page_ms_max = max(page_latencies, default=0.0)
            _update_sina_snapshot_health(
                status="healthy",
                rows=len(records),
                expected_count=expected_count,
                pages=total_pages,
                duration_ms=elapsed_ms,
                page_ms_avg=round(page_ms_avg, 2),
                page_ms_max=round(page_ms_max, 2),
                retried_pages=sum(1 for attempts in page_attempts if attempts > 1),
                error_type=None,
                error_message=None,
            )
            logger.info(
                "新浪全市场快照完整拉取: rows=%s expected=%s pages=%s workers=%s "
                "retried_pages=%s elapsed_ms=%.2f page_ms_avg=%.2f page_ms_max=%.2f",
                len(records), expected_count, total_pages, page_workers,
                sum(1 for attempts in page_attempts if attempts > 1),
                elapsed_ms, page_ms_avg, page_ms_max,
            )
            return records
        except Exception as error:
            _update_sina_snapshot_health(
                status="error",
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                error_type=type(error).__name__,
                error_message=str(error)[:1000],
            )
            raise

    def _fetch_market_hq_records(
        self,
        ttl: int | None = None,
        cache_scope: str = "default",
    ) -> list[dict]:
        """合并相同作用域的并发全市场快照请求。"""
        if ttl is None:
            return self._load_market_hq_records(ttl=ttl, cache_scope=cache_scope)
        cache_key = dated_cache_key("sina", "hq_records", cache_scope)
        return cast(
            list[dict],
            self._hq_singleflight.do(
                cache_key,
                lambda: self._load_market_hq_records(ttl=ttl, cache_scope=cache_scope),
            ),
        )

    def fetch_stock_intraday_minute_direct(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
        """直接拉取新浪个股分时分钟线（解析 JSONP 响应）。

        Param:
            code: 6 位股票代码，默认 000001
            date: 可选，交易日，格式 YYYY-MM-DD
        Return:
            标准化后的分时 DataFrame
        """
        sym = normalize_code(code)
        sina_code = sym.prefixed_lower
        params = {
            "symbol": sina_code,
            "callback": f"var t1{sina_code}",
            "version": "7.11.0",
            "dpc": "1",
        }
        response = self._session.get("https://cn.finance.sina.com.cn/minline/getMinlineData", params=params, timeout=10)
        response.raise_for_status()
        payload = parse_jsonp(response.text)
        rows = payload.get("result", {}).get("data", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame()
        trade_date = date or pd.Timestamp.now().strftime("%Y-%m-%d")
        result_df = pd.DataFrame(
            {
                "时间": df["m"].map(lambda value: f"{trade_date} {str(value).strip()}"),
                "成交价": pd.to_numeric(df.get("p"), errors="coerce"),
                "均价": pd.to_numeric(df.get("avg_p"), errors="coerce"),
                "成交量": pd.to_numeric(df.get("v"), errors="coerce"),
                "成交额": pd.to_numeric(df.get("p"), errors="coerce") * pd.to_numeric(df.get("v"), errors="coerce"),
            }
        )
        return normalize_intraday_df(result_df)


sina_provider = SinaDataProvider()
