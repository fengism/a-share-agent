"""A/H 股及主要指数市场日行情刷新器。"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time

import pandas as pd

from app.core.concurrency.rate_limiter import call_blocking, sina_semaphore
from app.core.market import SHANGHAI_TIMEZONE, safe_float
from app.domain.market import MarketIndices
from app.financial_data.hk.service import HKMarketService, hk_market_service
from app.financial_data.stock.quotes.sources import get_spot_source
from app.financial_data.stock.quotes.spot_snapshot import (
    _fetch_spot_akshare,
    _fetch_spot_east,
    _fetch_spot_sina_rank,
    _fetch_spot_sina_vip,
)
from app.infrastructure.providers.registry import get_provider
from app.modules.market_daily.models import CollectedMarketDailyBars, MarketDailyBarRecord

_CN_MIN_STOCK_COUNT = 3000
_HK_MIN_STOCK_COUNT = 1000


class SnapshotDateExpiredError(RuntimeError):
    """全市场快照已经推进到目标日之后，继续重试无法恢复历史个股。"""


def _first(row: pd.Series, *names: str):
    for name in names:
        if name in row and not pd.isna(row.get(name)):
            return row.get(name)
    return None


def _text(row: pd.Series, *names: str) -> str:
    value = _first(row, *names)
    return str(value).strip() if value is not None else ""


def _parse_quote_time(value: object, trade_date: date) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text):
        parsed = pd.to_datetime(f"{trade_date.isoformat()} {text}", errors="coerce")
    else:
        parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    timestamp = datetime.fromisoformat(parsed.isoformat())
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=SHANGHAI_TIMEZONE)
    return timestamp


def _change(close: float, pre_close: float | None) -> tuple[float | None, float | None]:
    if pre_close is None or pre_close <= 0:
        return None, None
    amount = close - pre_close
    return amount, amount / pre_close * 100


def _normalize_ohlc(
    close: float,
    open_price: float | None,
    high: float | None,
    low: float | None,
) -> tuple[float | None, float, float]:
    """将停牌/低流动性快照归一化为合法 OHLC，不改动真实收盘价。"""
    normalized_open = open_price if open_price is not None and open_price > 0 else None
    candidates = [close]
    if normalized_open is not None:
        candidates.append(normalized_open)
    normalized_high = max([value for value in (high, *candidates) if value is not None and value > 0])
    normalized_low = min([value for value in (low, *candidates) if value is not None and value > 0])
    return normalized_open, normalized_high, normalized_low


def normalize_cn_stocks(frame: pd.DataFrame, trade_date: date, source: str) -> list[MarketDailyBarRecord]:
    records: list[MarketDailyBarRecord] = []
    for _, row in frame.iterrows():
        code = _text(row, "代码", "code", "symbol")
        close = safe_float(_first(row, "最新价", "收盘", "close", "trade"))
        if len(code) != 6 or not code.isdigit() or close is None or close <= 0:
            continue
        pre_close = safe_float(_first(row, "昨收", "pre_close", "settlement"))
        change_amount, calculated_pct = _change(close, pre_close)
        open_price, high, low = _normalize_ohlc(
            close,
            safe_float(_first(row, "今开", "开盘", "open")),
            safe_float(_first(row, "最高", "high")),
            safe_float(_first(row, "最低", "low")),
        )
        records.append(MarketDailyBarRecord(
            market="cn",
            instrument_type="stock",
            code=code,
            name=_text(row, "名称", "name"),
            trade_date=trade_date,
            currency="CNY",
            open=open_price,
            high=high,
            low=low,
            close=close,
            pre_close=pre_close,
            change_amount=safe_float(_first(row, "涨跌额", "change")) or change_amount,
            change_pct=safe_float(_first(row, "涨跌幅", "change_pct", "changepercent")) or calculated_pct,
            volume=safe_float(_first(row, "成交量", "volume")),
            amount=safe_float(_first(row, "成交额", "amount")),
            source=source,
            source_quote_time=_parse_quote_time(_first(row, "日期时间", "更新时间", "time"), trade_date),
        ))
    return records


def normalize_hk_stocks(
    frame: pd.DataFrame,
    trade_date: date,
    source: str,
    *,
    require_trade_date: bool = False,
    require_closed_quote: bool = False,
) -> list[MarketDailyBarRecord]:
    records: list[MarketDailyBarRecord] = []
    for _, row in frame.iterrows():
        raw_code = _text(row, "代码", "symbol", "code")
        digits = raw_code.removeprefix("hk").removeprefix("HK")
        close = safe_float(_first(row, "最新价", "收盘", "close", "lasttrade"))
        if not digits.isdigit() or not 1 <= len(digits) <= 5 or close is None or close <= 0:
            continue
        code = digits.zfill(5)
        raw_quote_time = _first(row, "日期时间", "时间", "ticktime")
        source_quote_time = _parse_quote_time(raw_quote_time, trade_date)
        explicit_quote_date = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", str(raw_quote_time or ""))
        if (require_trade_date or require_closed_quote) and (
            source_quote_time is None
            or explicit_quote_date is None
            or source_quote_time.astimezone(SHANGHAI_TIMEZONE).date() != trade_date
        ):
            continue
        if (
            require_closed_quote
            and source_quote_time is not None
            and source_quote_time.astimezone(SHANGHAI_TIMEZONE).time() < time(16, 0)
        ):
            continue
        pre_close = safe_float(_first(row, "昨收", "pre_close", "prevclose"))
        change_amount, calculated_pct = _change(close, pre_close)
        open_price, high, low = _normalize_ohlc(
            close,
            safe_float(_first(row, "今开", "开盘", "open")),
            safe_float(_first(row, "最高", "high")),
            safe_float(_first(row, "最低", "low")),
        )
        records.append(MarketDailyBarRecord(
            market="hk",
            instrument_type="stock",
            code=code,
            name=_text(row, "中文名称", "名称", "name"),
            trade_date=trade_date,
            currency="HKD",
            open=open_price,
            high=high,
            low=low,
            close=close,
            pre_close=pre_close,
            change_amount=safe_float(_first(row, "涨跌额", "change", "pricechange")) or change_amount,
            change_pct=safe_float(_first(row, "涨跌幅", "change_pct", "changepercent")) or calculated_pct,
            volume=safe_float(_first(row, "成交量", "volume")),
            amount=safe_float(_first(row, "成交额", "amount")),
            source=source,
            source_quote_time=source_quote_time,
        ))
    return records


def normalize_indices(
    indices: MarketIndices,
    *,
    market: str,
    trade_date: date,
) -> list[MarketDailyBarRecord]:
    currency = "CNY" if market == "cn" else "HKD"
    source = indices.source or "unknown"
    records: list[MarketDailyBarRecord] = []
    for item in indices.indices:
        close = item.price
        if close is None or close <= 0:
            continue
        change_amount, calculated_pct = _change(close, item.pre_close)
        records.append(MarketDailyBarRecord(
            market=market,
            instrument_type="index",
            code=item.code,
            name=item.name,
            trade_date=trade_date,
            currency=currency,
            open=item.open,
            high=item.high,
            low=item.low,
            close=close,
            pre_close=item.pre_close,
            change_amount=change_amount,
            change_pct=item.change_pct if item.change_pct is not None else calculated_pct,
            volume=item.volume,
            amount=item.amount,
            source=source,
        ))
    return records


async def _verify_cn_trade_date(trade_date: date) -> None:
    """用独立逐笔行情日期确认全市场快照不是前一交易日缓存。"""
    provider = get_provider("sina")
    observed_dates: list[str] = []
    errors: list[str] = []
    for code in ("600519", "000001", "300750"):
        try:
            observed = await call_blocking(
                provider.fetch_last_trade_date,
                code,
                semaphore=sina_semaphore,
            )
        except Exception as error:
            errors.append(f"{code}:{type(error).__name__}")
            continue
        if observed:
            observed_dates.append(observed)
    target_text = trade_date.isoformat()
    # 必须先检查是否已有任一哨兵推进到下一交易日。个别停牌或低流动性标的
    # 可能仍返回目标日，不能因此提前放行已经切换日期的全市场快照。
    if any(observed > target_text for observed in observed_dates):
        raise SnapshotDateExpiredError(
            f"A 股全市场快照已推进到目标日之后: target={trade_date}, observed={observed_dates}"
        )
    if target_text in observed_dates:
        return
    raise RuntimeError(
        f"A 股行情日期尚未确认到 {trade_date}: observed={observed_dates}, errors={errors}"
    )


async def fetch_cn_stocks(trade_date: date) -> CollectedMarketDailyBars:
    """绕过五分钟文件缓存，按现有多源顺序抓取盘后全量 A 股。"""
    await _verify_cn_trade_date(trade_date)
    loaders: tuple[Callable[[], Awaitable[pd.DataFrame | None]], ...] = (
        _fetch_spot_sina_vip,
        _fetch_spot_sina_rank,
        _fetch_spot_east,
        _fetch_spot_akshare,
    )
    errors: list[str] = []
    for loader in loaders:
        try:
            frame = await loader()
        except Exception as error:  # pragma: no cover - loaders normally normalize failures
            errors.append(f"{loader.__name__}:{type(error).__name__}")
            continue
        if frame is None or frame.empty:
            errors.append(f"{loader.__name__}:empty")
            continue
        source = get_spot_source(frame)
        records = normalize_cn_stocks(frame, trade_date, source)
        if len(records) < _CN_MIN_STOCK_COUNT:
            errors.append(f"{source}:only-{len(records)}")
            continue
        return CollectedMarketDailyBars(segment="cn_stock", trade_date=trade_date, source=source, records=records)
    raise RuntimeError(f"A 股市场日行情不完整: {', '.join(errors)}")


async def _verify_hk_trade_date(trade_date: date, service: HKMarketService) -> None:
    """用带完整日期的 rt_hk 直查接口确认全量 time-only 快照属于目标交易日。"""
    frame = await service._call(
        "fetch_hk_stock_quotes_by_codes",
        service.provider.fetch_hk_stock_quotes_by_codes,
        ["00700", "00005", "09988"],
    )
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise RuntimeError("港股行情日期哨兵为空")
    observed = [
        str(value)
        for value in frame.get("日期时间", pd.Series(dtype="object")).tolist()
        if value is not None
    ]
    observed_dates = [
        match.group(0).replace("/", "-")
        for value in observed
        if (match := re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", value))
    ]
    if any(observed_date > trade_date.isoformat() for observed_date in observed_dates):
        raise SnapshotDateExpiredError(
            f"港股全市场快照已推进到目标日之后: target={trade_date}, observed={observed_dates[:3]}"
        )
    verified = normalize_hk_stocks(
        frame,
        trade_date,
        "sina_hk.realtime_sentinel",
        require_closed_quote=True,
    )
    if not verified:
        raise RuntimeError(f"港股行情日期尚未确认到 {trade_date} 16:00 后: observed={observed[:3]}")


def _attach_verified_hk_date(frame: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    """在哨兵已确认日期后，为仅含时间的全量行情补齐该日期。"""
    result = frame.copy()
    if "日期时间" not in result.columns:
        return result

    def attach(value: object) -> object:
        text = str(value or "").strip()
        if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text):
            return f"{trade_date.isoformat()} {text}"
        return value

    result["日期时间"] = result["日期时间"].map(attach)
    return result


async def fetch_hk_stocks(trade_date: date, service: HKMarketService = hk_market_service) -> CollectedMarketDailyBars:
    await _verify_hk_trade_date(trade_date, service)
    frame = await service._call("fetch_hk_stocks_spot", service.provider.fetch_hk_stocks_spot)
    if not isinstance(frame, pd.DataFrame):
        raise RuntimeError("港股市场日行情格式无效")
    frame = _attach_verified_hk_date(frame, trade_date)
    records = normalize_hk_stocks(
        frame,
        trade_date,
        "sina_hk.spot_snapshot",
        # 哨兵已经确认批次属于目标交易日；个别低流动性股票最后成交早于
        # 16:00 仍是合法收盘价，因此这里只校验日期，不按逐股成交时间丢弃。
        require_trade_date=True,
    )
    if len(records) < _HK_MIN_STOCK_COUNT:
        raise RuntimeError(f"港股当日 16:00 后市场日行情不完整: only-{len(records)}")
    return CollectedMarketDailyBars(segment="hk_stock", trade_date=trade_date, source="sina_hk.spot_snapshot", records=records)


async def fetch_cn_indices(trade_date: date) -> CollectedMarketDailyBars:
    """从当日日线读取指数收盘价，避免将实时页的盘中价格写入收盘库。"""
    await _verify_cn_trade_date(trade_date)
    from app.financial_data.market.quotes.index_kline import _load_index_kline

    index_names = {
        "000001": "上证指数",
        "399001": "深证成指",
        "399006": "创业板指",
        "000688": "科创50",
        "000300": "沪深300",
        "000905": "中证500",
        "000852": "中证1000",
    }
    records: list[MarketDailyBarRecord] = []
    errors: list[str] = []
    target_text = trade_date.isoformat()
    for symbol, name in index_names.items():
        try:
            data = await _load_index_kline(symbol, "daily", target_text, target_text)
        except Exception as error:
            errors.append(f"{symbol}:{type(error).__name__}")
            continue
        item = next((item for item in data.items if item.date == target_text), None)
        if item is None or item.close <= 0:
            errors.append(f"{symbol}:missing")
            continue
        records.append(MarketDailyBarRecord(
            market="cn",
            instrument_type="index",
            code=symbol,
            name=name,
            trade_date=trade_date,
            currency="CNY",
            open=item.open,
            high=item.high,
            low=item.low,
            close=item.close,
            pre_close=item.pre_close,
            change_pct=item.change_pct,
            volume=item.volume,
            amount=item.amount,
            source=data.source or "index_kline",
        ))
    if len(records) != len(index_names):
        raise RuntimeError(
            f"A 股指数当日日线不完整: {len(records)}/{len(index_names)}; {', '.join(errors)}"
        )
    return CollectedMarketDailyBars(
        segment="cn_index", trade_date=trade_date, source="index_kline", records=records
    )


async def fetch_hk_indices(trade_date: date, service: HKMarketService = hk_market_service) -> CollectedMarketDailyBars:
    records: list[MarketDailyBarRecord] = []
    for symbol in ("HSI", "HSCEI", "HSTECH"):
        frame = await service._call(
            "fetch_hk_index_daily",
            service.provider.fetch_hk_index_daily,
            symbol,
        )
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        normalized = frame.rename(columns={
            "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
            "收盘": "close", "成交量": "volume", "成交额": "amount",
        }).copy()
        if "date" not in normalized.columns or "close" not in normalized.columns:
            continue
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date"]).sort_values("date")
        if normalized.empty:
            continue
        target_rows = normalized[normalized["date"].dt.date == trade_date]
        if target_rows.empty:
            continue
        row = target_rows.iloc[-1]
        close = safe_float(row.get("close"))
        if close is None or close <= 0:
            continue
        records.append(MarketDailyBarRecord(
            market="hk",
            instrument_type="index",
            code=symbol,
            name=symbol,
            trade_date=trade_date,
            currency="HKD",
            open=safe_float(row.get("open")),
            high=safe_float(row.get("high")),
            low=safe_float(row.get("low")),
            close=close,
            volume=safe_float(row.get("volume")),
            amount=safe_float(row.get("amount")),
            source="sina_hk.index_daily",
        ))
    if len(records) != 3:
        raise RuntimeError(f"港股指数当日市场日行情不完整: {len(records)}/3")
    return CollectedMarketDailyBars(
        segment="hk_index", trade_date=trade_date, source="sina_hk.index_daily", records=records
    )


async def collect_segment(segment: str, trade_date: date) -> CollectedMarketDailyBars:
    collectors: dict[str, Callable[[date], Awaitable[CollectedMarketDailyBars]]] = {
        "cn_stock": fetch_cn_stocks,
        "cn_index": fetch_cn_indices,
        "hk_stock": fetch_hk_stocks,
        "hk_index": fetch_hk_indices,
    }
    try:
        collector = collectors[segment]
    except KeyError as error:
        raise ValueError(f"未知市场日行情分区: {segment}") from error
    return await collector(trade_date)
