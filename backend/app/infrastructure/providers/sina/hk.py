"""Sina Hong Kong market adapter using AkShare's maintained Sina decoders."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import akshare as ak
import pandas as pd
import requests
from akshare.index import index_stock_hk
from akshare.stock import stock_hk_sina

from app.core.exceptions import UpstreamUnavailableError
from app.infrastructure.javascript_runtime import register_shutdown_guard_fallback

logger = logging.getLogger(__name__)

# 本模块直接 import akshare（也就直接用到 MiniRacer），兜底 guard 必须在这里生效。
register_shutdown_guard_fallback()

try:
    from py_mini_racer._mini_racer import MiniRacer as _ModernMiniRacer
except ImportError:  # pragma: no cover - compatibility with legacy py-mini-racer
    _ModernMiniRacer = None

_HK_STOCK_DATA_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHKStockData"
)
_HK_STOCK_COUNT_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHKStockCount"
)
_HK_REALTIME_URL = "https://hq.sinajs.cn/list="
_HK_REALTIME_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}
_HK_REALTIME_BATCH_SIZE = 50
_HK_SOURCE_PAGE_SIZE = 60
_HK_MAX_SOURCE_PAGE = 99
_HK_BATCH_SIZE = 24
_HK_MAX_WORKERS = 12
_HK_REQUEST_TIMEOUT_SECONDS = 10


def _to_float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

_HK_STOCK_COLUMNS = {
    "ticktime": "日期时间",
    "symbol": "代码",
    "name": "中文名称",
    "engname": "英文名称",
    "tradetype": "交易类型",
    "lasttrade": "最新价",
    "pricechange": "涨跌额",
    "changepercent": "涨跌幅",
    "prevclose": "昨收",
    "open": "今开",
    "high": "最高",
    "low": "最低",
    "volume": "成交量",
    "amount": "成交额",
    "buy": "买一",
    "sell": "卖一",
    "pe_ratio": "市盈率",
}
_HK_STOCK_OUTPUT_COLUMNS = list(dict.fromkeys(_HK_STOCK_COLUMNS.values()))
_HK_STOCK_NUMERIC_COLUMNS = [
    "最新价",
    "涨跌额",
    "涨跌幅",
    "昨收",
    "今开",
    "最高",
    "最低",
    "成交量",
    "成交额",
    "买一",
    "卖一",
    "市盈率",
]


def _empty_hk_stock_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_HK_STOCK_OUTPUT_COLUMNS)


def _normalize_hk_stock_records(records: object) -> pd.DataFrame:
    if not isinstance(records, list) or not records:
        return _empty_hk_stock_frame()
    frame = pd.DataFrame(records).rename(columns=_HK_STOCK_COLUMNS)
    for column in _HK_STOCK_OUTPUT_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[_HK_STOCK_OUTPUT_COLUMNS].copy()
    for column in _HK_STOCK_NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _activate_compatible_mini_racer() -> None:
    """Make AkShare use the MiniRacer wrapper matching its installed library."""
    if _ModernMiniRacer is None:
        return

    stock_hk_sina.MiniRacer = _ModernMiniRacer
    index_stock_hk.py_mini_racer.MiniRacer = _ModernMiniRacer


class SinaHKProvider:
    name = "sina"

    def __init__(self, request_get: Callable[..., requests.Response] = requests.get) -> None:
        self._request_get = request_get

    @staticmethod
    def _stock_page_params(page: int) -> dict[str, str]:
        return {
            "page": str(page),
            "num": str(_HK_SOURCE_PAGE_SIZE),
            "sort": "symbol",
            "asc": "1",
            "node": "qbgg_hk",
            "_s_r_a": "init",
        }

    def _fetch_stock_source_page(self, page: int) -> pd.DataFrame:
        response = self._request_get(
            _HK_STOCK_DATA_URL,
            params=self._stock_page_params(page),
            timeout=_HK_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return _normalize_hk_stock_records(response.json())

    def _fetch_stock_count(self) -> int:
        response = self._request_get(
            _HK_STOCK_COUNT_URL,
            params={"node": "qbgg_hk"},
            timeout=_HK_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        try:
            return max(0, int(response.json()))
        except (TypeError, ValueError):
            return 0

    def _fetch_stock_source_pages(self, pages: Iterable[int]) -> dict[int, pd.DataFrame]:
        """并发抓取指定源页；单页失败仅跳过并告警，不中断整批。"""
        page_numbers = list(pages)
        if not page_numbers:
            return {}
        frames: dict[int, pd.DataFrame] = {}
        with ThreadPoolExecutor(
            max_workers=min(_HK_MAX_WORKERS, len(page_numbers)),
            thread_name_prefix="sina-hk-spot",
        ) as executor:
            futures = {
                page: executor.submit(self._fetch_stock_source_page, page)
                for page in page_numbers
            }
            for page, future in futures.items():
                try:
                    frames[page] = future.result()
                except Exception as exc:
                    logger.warning("新浪港股行情第 %s 页抓取失败，跳过该页: %s", page, exc)
        return frames

    def fetch_hk_stocks_spot(self) -> pd.DataFrame:
        collected: list[pd.DataFrame] = []
        for start in range(1, _HK_MAX_SOURCE_PAGE + 1, _HK_BATCH_SIZE):
            stop = min(start + _HK_BATCH_SIZE, _HK_MAX_SOURCE_PAGE + 1)
            frames = self._fetch_stock_source_pages(range(start, stop))
            for page in range(start, stop):
                frame = frames.get(page)
                if frame is None:
                    continue
                if frame.empty:
                    return pd.concat(collected, ignore_index=True) if collected else frame
                collected.append(frame)
        if not collected:
            raise UpstreamUnavailableError("新浪港股实时行情全部页面抓取失败")
        return pd.concat(collected, ignore_index=True)

    def fetch_hk_stocks_spot_page(
        self,
        page: int,
        page_size: int,
    ) -> tuple[pd.DataFrame, int]:
        start = (page - 1) * page_size
        end = start + page_size
        first_source_page = start // _HK_SOURCE_PAGE_SIZE + 1
        last_source_page = (end - 1) // _HK_SOURCE_PAGE_SIZE + 1
        source_pages = list(range(first_source_page, last_source_page + 1))

        with ThreadPoolExecutor(
            max_workers=min(_HK_MAX_WORKERS, len(source_pages) + 1),
            thread_name_prefix="sina-hk-page",
        ) as executor:
            count_future = executor.submit(self._fetch_stock_count)
            page_futures = {
                source_page: executor.submit(self._fetch_stock_source_page, source_page)
                for source_page in source_pages
            }
            try:
                reported_total = count_future.result()
            except Exception as exc:
                logger.warning("新浪港股总数查询失败: %s", exc)
                reported_total = 0
            frames: dict[int, pd.DataFrame] = {}
            for source_page, future in page_futures.items():
                try:
                    frames[source_page] = future.result()
                except Exception as exc:
                    logger.warning("新浪港股行情第 %s 页抓取失败，跳过该页: %s", source_page, exc)
        if not frames:
            raise UpstreamUnavailableError("新浪港股实时行情页面抓取失败")

        merged = pd.concat(frames.values(), ignore_index=True)
        offset = start - (first_source_page - 1) * _HK_SOURCE_PAGE_SIZE
        result = merged.iloc[offset:offset + page_size].reset_index(drop=True)
        last_frame = frames.get(last_source_page, _empty_hk_stock_frame())
        if len(last_frame) == _HK_SOURCE_PAGE_SIZE:
            total = max(reported_total, end + 1)
        elif not last_frame.empty:
            total = (last_source_page - 1) * _HK_SOURCE_PAGE_SIZE + len(last_frame)
        else:
            total = reported_total
        return result, total

    def fetch_hk_stock_quotes_by_codes(self, codes: Sequence[str]) -> pd.DataFrame:
        """按代码批量直查新浪 rt_hk 实时行情，避免为几只股票拉取全量 99 页。

        行布局（2026-09 实测）：0 英文名 / 1 中文名 / 2 今开 / 3 昨收 / 4 最高 /
        5 最低 / 6 最新价 / 7 涨跌额 / 8 涨跌幅% / 9 买一 / 10 卖一 / 11 成交额 /
        12 成交量 / 17 日期 / 18 时间；涨跌额与涨跌幅已交叉验证。
        """
        normalized: list[str] = []
        seen: set[str] = set()
        for code in codes:
            digits = str(code).strip()
            if not digits.isdigit() or not 1 <= len(digits) <= 5:
                continue
            padded = digits.zfill(5)
            if padded not in seen:
                seen.add(padded)
                normalized.append(padded)
        if not normalized:
            return _empty_hk_stock_frame()

        rows: list[dict[str, Any]] = []
        for chunk_start in range(0, len(normalized), _HK_REALTIME_BATCH_SIZE):
            chunk = normalized[chunk_start:chunk_start + _HK_REALTIME_BATCH_SIZE]
            response = self._request_get(
                _HK_REALTIME_URL + ",".join(f"rt_hk{code}" for code in chunk),
                headers=_HK_REALTIME_HEADERS,
                timeout=_HK_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            for line in response.text.strip().split("\n"):
                if "=" not in line or '"' not in line:
                    continue
                fields = line.split('"')[1].split(",")
                if len(fields) < 19 or not fields[1]:
                    continue
                code = line.split("=")[0].split("rt_hk")[-1]
                rows.append({
                    "代码": code,
                    "中文名称": fields[1],
                    "英文名称": fields[0],
                    "最新价": _to_float_or_none(fields[6]),
                    "涨跌额": _to_float_or_none(fields[7]),
                    "涨跌幅": _to_float_or_none(fields[8]),
                    "昨收": _to_float_or_none(fields[3]),
                    "今开": _to_float_or_none(fields[2]),
                    "最高": _to_float_or_none(fields[4]),
                    "最低": _to_float_or_none(fields[5]),
                    "成交量": _to_float_or_none(fields[12]),
                    "成交额": _to_float_or_none(fields[11]),
                    "买一": _to_float_or_none(fields[9]),
                    "卖一": _to_float_or_none(fields[10]),
                    "市盈率": _to_float_or_none(fields[13]) if len(fields) > 13 else None,
                    "日期时间": f"{fields[17].replace('/', '-')} {fields[18]}",
                })
        if not rows:
            return _empty_hk_stock_frame()
        return pd.DataFrame(rows, columns=_HK_STOCK_OUTPUT_COLUMNS)

    def fetch_hk_stock_daily(self, code: str, adjust: str = "") -> pd.DataFrame:
        _activate_compatible_mini_racer()
        return ak.stock_hk_daily(symbol=code, adjust=adjust)

    def fetch_hk_indices_spot(self) -> pd.DataFrame:
        return ak.stock_hk_index_spot_sina()

    def fetch_hk_index_daily(self, symbol: str) -> pd.DataFrame:
        _activate_compatible_mini_racer()
        return ak.stock_hk_index_daily_sina(symbol=symbol)


sina_hk_provider = SinaHKProvider()
