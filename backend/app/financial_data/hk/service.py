from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

import pandas as pd

from app.core.cache import market_cache, series_cache
from app.core.concurrency.rate_limiter import call_blocking, sina_semaphore
from app.core.exceptions import InvalidRequestError, UpstreamUnavailableError
from app.core.market import safe_float
from app.domain.market import IndexItem, KlineData, KlineItem, MarketIndices
from app.financial_data.hk.schemas import (
    HKStockQuote,
    HKStockQuotePage,
    HKStockSearchItem,
    HKStockSearchResult,
)
from app.financial_data.hk.search_index import HKStockSearchIndex, hk_stock_search_index
from app.infrastructure.providers.registry import get_provider

_HK_CODE_PATTERN = re.compile(r"^(?:hk)?(\d{1,5})$", re.IGNORECASE)
_HK_INDEX_SYMBOLS = frozenset({"HSI", "HSCEI", "HSTECH"})
_PERIODS = frozenset({"daily", "weekly", "monthly"})
_ADJUSTMENTS = frozenset({"none", "qfq", "hfq"})


class HKProvider(Protocol):
    def fetch_hk_stocks_spot(self) -> pd.DataFrame: ...
    def fetch_hk_stocks_spot_page(self, page: int, page_size: int) -> tuple[pd.DataFrame, int]: ...
    def fetch_hk_stock_daily(self, code: str, adjust: str) -> pd.DataFrame: ...
    def fetch_hk_indices_spot(self) -> pd.DataFrame: ...
    def fetch_hk_index_daily(self, symbol: str) -> pd.DataFrame: ...


def normalize_hk_code(code: str) -> str:
    value = str(code or "").strip()
    match = _HK_CODE_PATTERN.fullmatch(value)
    if not match:
        raise InvalidRequestError("港股代码格式无效，请输入 1-5 位数字，例如 00700")
    digits = match.group(1)
    if len(digits) > 5:
        raise InvalidRequestError("港股代码格式无效，请输入 1-5 位数字，例如 00700")
    return digits.zfill(5)


def normalize_hk_index_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if value not in _HK_INDEX_SYMBOLS:
        raise InvalidRequestError("港股指数仅支持 HSI、HSCEI、HSTECH")
    return value


def _validate_period(period: str) -> str:
    value = str(period or "").strip().lower()
    if value not in _PERIODS:
        raise InvalidRequestError("period 仅支持 daily、weekly、monthly")
    return value


def _validate_adjust(adjust: str) -> str:
    value = str(adjust or "none").strip().lower()
    if value not in _ADJUSTMENTS:
        raise InvalidRequestError("adjust 仅支持 none、qfq、hfq")
    return value


def _parse_boundary(value: str, field: str) -> pd.Timestamp | None:
    if not value:
        return None
    timestamp = pd.to_datetime(value, format="mixed", errors="coerce")
    if pd.isna(timestamp):
        raise InvalidRequestError(f"{field} 日期格式无效")
    return timestamp


def _first_text(row: pd.Series, *columns: str) -> str | None:
    for column in columns:
        value = row.get(column)
        if value is not None and not pd.isna(value):
            text = str(value).strip()
            if text:
                return text
    return None


def _normalize_history_frame(data: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
    aliases = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
    }
    frame = data.rename(columns=aliases).copy()
    required = {"date", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError(f"新浪港股历史行情缺少字段: {sorted(required - set(frame.columns))}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume", "amount"):
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date")
    start = _parse_boundary(start_date, "start_date")
    end = _parse_boundary(end_date, "end_date")
    if start is not None:
        frame = frame[frame["date"] >= start]
    if end is not None:
        frame = frame[frame["date"] <= end]
    return frame.reset_index(drop=True)


def _resample_history(frame: pd.DataFrame, period: str) -> pd.DataFrame:
    if period == "daily" or frame.empty:
        return frame
    frequency = "W-FRI" if period == "weekly" else "M"
    grouped = frame.assign(_bucket=frame["date"].dt.to_period(frequency)).groupby("_bucket", sort=True)
    return grouped.agg(
        date=("date", "max"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        amount=("amount", "sum"),
    ).reset_index(drop=True)


def _to_kline(code: str, period: str, adjust: str, frame: pd.DataFrame) -> KlineData:
    items = [
        KlineItem(
            code=code,
            date=row["date"].strftime("%Y-%m-%d"),
            open=float(row["open"]),
            close=float(row["close"]),
            high=float(row["high"]),
            low=float(row["low"]),
            volume=float(row["volume"] or 0),
            amount=float(row["amount"] or 0),
        )
        for _, row in frame.iterrows()
    ]
    return KlineData(
        code=code,
        period=period,
        adjust=adjust,
        source="sina",
        adjustment_verified=adjust in {"qfq", "hfq"},
        items=items,
    )


class HKMarketService:
    def __init__(
        self,
        provider: HKProvider | None = None,
        search_index: HKStockSearchIndex | None = None,
    ) -> None:
        self._provider = provider
        self._search_index = search_index
        self._cache_enabled = provider is None

    @property
    def provider(self) -> HKProvider:
        return self._provider or get_provider("sina_hk")

    async def _call(self, function, *args):
        try:
            return await call_blocking(function, *args, semaphore=sina_semaphore)
        except InvalidRequestError:
            raise
        except Exception as error:
            raise UpstreamUnavailableError("新浪港股行情暂时不可用") from error

    async def _stock_frame(self) -> pd.DataFrame:
        key = "hk:stocks:spot"
        if self._cache_enabled:
            cached = market_cache.get(key)
            if isinstance(cached, pd.DataFrame):
                return cached.copy()
        frame = await self._call(self.provider.fetch_hk_stocks_spot)
        if not isinstance(frame, pd.DataFrame):
            raise UpstreamUnavailableError("新浪港股实时行情返回格式异常")
        if self._cache_enabled:
            market_cache.set(key, frame.copy(), ttl=60)
        return frame

    async def _stock_page(self, page: int, page_size: int) -> tuple[pd.DataFrame, int] | None:
        fetch_page = getattr(self.provider, "fetch_hk_stocks_spot_page", None)
        if not callable(fetch_page):
            return None
        result = await self._call(fetch_page, page, page_size)
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not isinstance(result[0], pd.DataFrame)
            or not isinstance(result[1], int)
        ):
            raise UpstreamUnavailableError("新浪港股实时行情返回格式异常")
        return result

    async def _quotes_frame_for_codes(self, codes: Sequence[str]) -> pd.DataFrame:
        """按代码直查实时行情，避免为少数几只股票触发全量 99 页抓取。"""
        fetch_by_codes = getattr(self.provider, "fetch_hk_stock_quotes_by_codes", None)
        if not callable(fetch_by_codes):
            return await self._stock_frame()
        return await self._call(fetch_by_codes, list(codes))

    @property
    def search_index(self) -> HKStockSearchIndex:
        if self._search_index is None:
            self._search_index = (
                hk_stock_search_index
                if self._provider is None
                else HKStockSearchIndex(provider=self.provider)
            )
        return self._search_index

    async def search_stocks(self, query: str, *, limit: int = 8) -> HKStockSearchResult:
        records = await self.search_index.search(query, limit=limit)
        return HKStockSearchResult(
            items=[
                HKStockSearchItem(
                    code=record.code,
                    name=record.name,
                    english_name=record.english_name,
                )
                for record in records
            ]
        )

    async def get_stock_quotes(
        self,
        *,
        codes: Sequence[str] | None = None,
        query: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> HKStockQuotePage:
        normalized_codes = {normalize_hk_code(code) for code in (codes or [])}
        keyword = query.strip().lower()
        if normalized_codes and not keyword:
            frame = await self._quotes_frame_for_codes(sorted(normalized_codes))
            upstream_total = None
        else:
            paged_result = None
            if not normalized_codes and not keyword:
                paged_result = await self._stock_page(page, page_size)
            if paged_result is None:
                frame = await self._stock_frame()
                upstream_total = None
            else:
                frame, upstream_total = paged_result
        items: list[HKStockQuote] = []
        for _, row in frame.iterrows():
            raw_code = _first_text(row, "代码", "symbol", "code")
            try:
                code = normalize_hk_code(raw_code or "")
            except InvalidRequestError:
                continue
            name = _first_text(row, "中文名称", "名称", "name") or ""
            english_name = _first_text(row, "英文名称", "engname")
            if normalized_codes and code not in normalized_codes:
                continue
            if keyword and keyword not in code.lower() and keyword not in name.lower() and keyword not in (english_name or "").lower():
                continue
            items.append(HKStockQuote(
                code=code,
                name=name,
                english_name=english_name,
                trade_type=_first_text(row, "交易类型", "type"),
                price=safe_float(row.get("最新价")),
                change=safe_float(row.get("涨跌额")),
                change_pct=safe_float(row.get("涨跌幅")),
                pre_close=safe_float(row.get("昨收")),
                open=safe_float(row.get("今开")),
                high=safe_float(row.get("最高")),
                low=safe_float(row.get("最低")),
                volume=safe_float(row.get("成交量")),
                amount=safe_float(row.get("成交额")),
                bid=safe_float(row.get("买一")),
                ask=safe_float(row.get("卖一")),
                updated_at=_first_text(row, "日期时间", "时间"),
            ))
        if upstream_total is None:
            total = len(items)
            start = (page - 1) * page_size
            page_items = items[start:start + page_size]
        else:
            total = upstream_total
            page_items = items
        updated_at = next((item.updated_at for item in page_items if item.updated_at), None)
        return HKStockQuotePage(
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            source="sina",
            updated_at=updated_at,
        )

    async def get_stock_history(
        self,
        code: str,
        *,
        period: str = "daily",
        adjust: str = "none",
        start_date: str = "",
        end_date: str = "",
    ) -> KlineData:
        normalized_code = normalize_hk_code(code)
        normalized_period = _validate_period(period)
        normalized_adjust = _validate_adjust(adjust)
        key = f"hk:stock:history:{normalized_code}:{normalized_period}:{normalized_adjust}:{start_date}:{end_date}"
        if self._cache_enabled:
            cached = series_cache.get(key)
            if isinstance(cached, KlineData):
                return cached
        upstream_adjust = "" if normalized_adjust == "none" else normalized_adjust
        frame = await self._call(self.provider.fetch_hk_stock_daily, normalized_code, upstream_adjust)
        try:
            normalized = _normalize_history_frame(frame, start_date, end_date)
            result = _to_kline(
                normalized_code,
                normalized_period,
                normalized_adjust,
                _resample_history(normalized, normalized_period),
            )
        except InvalidRequestError:
            raise
        except Exception as error:
            raise UpstreamUnavailableError("新浪港股历史行情返回格式异常") from error
        if self._cache_enabled:
            series_cache.set(key, result, ttl=300)
        return result

    async def get_index_quotes(self, symbols: Sequence[str] | None = None) -> MarketIndices:
        normalized_symbols = [normalize_hk_index_symbol(symbol) for symbol in symbols] if symbols else []
        key = "hk:indices:spot"
        frame = market_cache.get(key) if self._cache_enabled else None
        if not isinstance(frame, pd.DataFrame):
            frame = await self._call(self.provider.fetch_hk_indices_spot)
            if not isinstance(frame, pd.DataFrame):
                raise UpstreamUnavailableError("新浪港股指数实时行情返回格式异常")
            if self._cache_enabled:
                market_cache.set(key, frame.copy(), ttl=30)
        wanted = set(normalized_symbols)
        indices: list[IndexItem] = []
        for _, row in frame.iterrows():
            symbol = (_first_text(row, "代码", "symbol") or "").upper()
            if symbol not in _HK_INDEX_SYMBOLS or (wanted and symbol not in wanted):
                continue
            indices.append(IndexItem(
                code=symbol,
                name=_first_text(row, "名称", "name") or symbol,
                price=safe_float(row.get("最新价")),
                change_pct=safe_float(row.get("涨跌幅")),
                pre_close=safe_float(row.get("昨收")),
                open=safe_float(row.get("今开")),
                high=safe_float(row.get("最高")),
                low=safe_float(row.get("最低")),
            ))
        order = normalized_symbols or ["HSI", "HSCEI", "HSTECH"]
        indices.sort(key=lambda item: order.index(item.code) if item.code in order else len(order))
        return MarketIndices(indices=indices, source="sina")

    async def get_index_history(
        self,
        symbol: str,
        *,
        period: str = "daily",
        start_date: str = "",
        end_date: str = "",
    ) -> KlineData:
        normalized_symbol = normalize_hk_index_symbol(symbol)
        normalized_period = _validate_period(period)
        key = f"hk:index:history:{normalized_symbol}:{normalized_period}:{start_date}:{end_date}"
        if self._cache_enabled:
            cached = series_cache.get(key)
            if isinstance(cached, KlineData):
                return cached
        frame = await self._call(self.provider.fetch_hk_index_daily, normalized_symbol)
        try:
            normalized = _normalize_history_frame(frame, start_date, end_date)
            result = _to_kline(
                normalized_symbol,
                normalized_period,
                "none",
                _resample_history(normalized, normalized_period),
            )
        except InvalidRequestError:
            raise
        except Exception as error:
            raise UpstreamUnavailableError("新浪港股指数历史行情返回格式异常") from error
        if self._cache_enabled:
            series_cache.set(key, result, ttl=300)
        return result


hk_market_service = HKMarketService()
