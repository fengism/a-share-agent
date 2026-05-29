import asyncio
import logging

import pandas as pd

from app.models.stock import KlineData, KlineItem
from app.services.base.provider_chain import BaseProviderChain, ProviderAttempt
from app.services.providers.akshare import akshare_provider as _akshare_provider
from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.services.providers.tdx import tdx_provider
from app.utils.cache import cache, cache_date, dated_cache_key, one_year_ago_date
from app.utils.market_utils import filter_index_hist_range
from app.utils.rate_limiter import call_blocking
from app.utils.data_clean import safe_float

logger = logging.getLogger(__name__)


async def _load_and_filter(fetch_fn, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = await call_blocking(fetch_fn, symbol=symbol)
    return await asyncio.to_thread(filter_index_hist_range, df, start_date, end_date)



def _build_index_kline_source_attempts(symbol: str, period: str, start_date: str, end_date: str) -> list[ProviderAttempt]:
    return [
        ProviderAttempt(
            label="TDX 指数K线",
            loader=lambda: call_blocking(tdx_provider.fetch_index_kline, symbol=symbol, start_date=start_date, end_date=end_date),
            on_error=f"TDX 指数K线不可用，尝试 Akshare 东方财富指数K线: symbol={symbol}",
        ),
        ProviderAttempt(
            label="Akshare 东方财富指数K线",
            loader=lambda: call_blocking(_akshare_provider.fetch_index_kline, symbol=symbol, period=period, start_date=start_date, end_date=end_date),
            on_error=f"Akshare 东方财富指数K线不可用，尝试 Akshare 新浪指数K线: symbol={symbol}",
        ),
        ProviderAttempt(
            label="Akshare 新浪指数K线",
            loader=lambda: _load_and_filter(_akshare_provider.fetch_index_kline_sina, symbol, start_date, end_date),
            on_error=f"Akshare 新浪指数K线不可用，尝试 Akshare 腾讯指数K线: symbol={symbol}",
        ),
        ProviderAttempt(
            label="Akshare 腾讯指数K线",
            loader=lambda: _load_and_filter(_akshare_provider.fetch_index_kline_tencent, symbol, start_date, end_date),
            on_error=f"Akshare 腾讯指数K线不可用，尝试东方财富指数K线直连: symbol={symbol}",
        ),
        ProviderAttempt(
            label="东方财富指数K线直连",
            loader=lambda: call_blocking(_eastmoney_provider.fetch_index_kline_direct, symbol, period, start_date, end_date),
        ),
    ]


def _to_kline_data(symbol: str, period: str, df: pd.DataFrame) -> KlineData:
    items: list[KlineItem] = []
    for _, row in df.iterrows():
        items.append(
            KlineItem(
                code=symbol,
                date=str(row.get("日期", row.get("date", ""))).replace("-", ""),
                open=float(row.get("开盘", row.get("open", 0)) or 0),
                close=float(row.get("收盘", row.get("close", 0)) or 0),
                high=float(row.get("最高", row.get("high", 0)) or 0),
                low=float(row.get("最低", row.get("low", 0)) or 0),
                volume=safe_float(row.get("成交量", row.get("volume"))) or 0,
                amount=safe_float(row.get("成交额", row.get("amount"))) or 0,
                amplitude=safe_float(row.get("振幅", row.get("amplitude"))),
                turnover_pct=safe_float(row.get("换手率", row.get("turnover_pct"))),
                pre_close=safe_float(row.get("涨跌幅", row.get("change_pct"))),
            )
        )
    return KlineData(code=symbol, period=period, adjust="", items=items)


async def get_index_kline(symbol: str, period: str = "daily", start_date: str = "", end_date: str = "") -> KlineData:
    if not end_date:
        end_date = cache_date()
    if not start_date:
        start_date = one_year_ago_date()

    cache_key = dated_cache_key("market_index_kline", symbol, period, start_date, end_date)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    df = await BaseProviderChain(_build_index_kline_source_attempts(symbol, period, start_date, end_date)).run()

    result = _to_kline_data(symbol, period, df)
    logger.info(f"指数K线获取成功: symbol={symbol}, items={len(result.items)}")
    cache.set(cache_key, result, ttl=300)
    return result
