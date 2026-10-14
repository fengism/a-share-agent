import asyncio
import logging
from collections.abc import Awaitable
from datetime import date

import pandas as pd

from app.core.cache import cache_date, dated_cache_key_no_day, one_year_ago_date, series_cache
from app.core.concurrency.rate_limiter import (
    akshare_semaphore,
    call_blocking,
    eastmoney_semaphore,
    tdx_semaphore,
    tencent_semaphore,
)
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamEmptyResponseError, UpstreamUnavailableError
from app.core.market import normalize_index_code, safe_float
from app.domain.market import KlineData, KlineItem
from app.financial_data.dates import clamp_kline_history_start_date as _clamp_start_date
from app.financial_data.dates import parse_market_date
from app.financial_data.kline_quality import validate_kline_frame
from app.financial_data.market.quotes.normalization import filter_index_hist_range
from app.financial_data.market.trading_session import (
    LIVE_MARKET_DATA_CACHE_TTL_SECONDS,
    resolve_market_data_cache_policy,
)
from app.financial_data.stock.quotes.historical import _resample_adjusted_daily_frame
from app.financial_data.stock.quotes.kline import (
    _merge_upstream_parts,
    _upstream_windows,
)
from app.infrastructure.providers.provider_chain import BaseProviderChain, ProviderAttempt
from app.infrastructure.providers.registry import get_provider
from app.modules.market_daily.reader import load_local_daily_kline, merge_local_daily_kline

logger = logging.getLogger(__name__)


def _get_akshare_provider():
    """Lazily resolve the Akshare provider singleton."""
    return get_provider("akshare")


def _get_eastmoney_provider():
    """Lazily resolve the EastMoney provider singleton."""
    return get_provider("eastmoney")


def _get_tdxhub_provider():
    """Lazily resolve the TDXHub provider singleton."""
    return get_provider("tdxhub")


def _get_tencent_provider():
    """Lazily resolve the Tencent provider singleton."""
    return get_provider("tencent")


_index_kline_singleflight = AsyncSingleFlight[KlineData]()


async def _load_and_filter(fetch_fn, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """加载指数历史数据并按日期范围过滤。

    Param:
        fetch_fn: 同步数据获取函数
        symbol: 指数代码
        start_date: 起始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
    Return:
        过滤后的 DataFrame
    """
    df = await call_blocking(fetch_fn, symbol=symbol)
    return await asyncio.to_thread(filter_index_hist_range, df, start_date, end_date)


async def _require_index_kline_frame(
    source: str,
    loader: Awaitable[pd.DataFrame],
    *,
    period: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """加载单个指数 K 线数据源，并将空结果视为失败。

    指数必然有完整历史（不存在"次新指数"），因此开启覆盖度校验：上游只回最近
    一两根时，其余校验都拦不住——陈旧度只看最新一根，而缓存键又含完整起止区间，
    残缺结果会被当成整段历史写入 ``series_cache``。
    """
    frame = await loader
    if frame.empty:
        # 上游 200 但没有可用 K 线（限流/截断），与永久失败区分开才能让熔断器计数。
        raise UpstreamEmptyResponseError(f"{source} 未返回有效指数 K 线")
    return validate_kline_frame(
        source,
        frame,
        start_date=start_date,
        end_date=end_date,
        period=period,
        require_coverage=True,
    )


def _build_index_kline_source_attempts(
    symbol: str, period: str, start_date: str, end_date: str
) -> list[ProviderAttempt[pd.DataFrame]]:
    """构造指数 K 线多数据源回退链。

    * daily：直接请求各数据源。
    * weekly / monthly / annual：先从日线数据源取全量日线，再本地聚合为目标周期；
      确保 K 线边界与真实交易日对齐，并与个股周/月/年线使用完全相同的合成逻辑。
      东财直连与 AkShare 东财接口作为 fallback（它们原生支持非日线，但依赖外部 API）。

    Param:
        symbol: 指数代码
        period: K 线周期标识
        start_date: 起始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
    Return:
        Provider 尝试列表，按优先级排序
    """
    if period == "daily":
        # ── 日线：直接请求各数据源（优先腾讯财经极速接口，无单线程互斥锁且按需切片）──────
        return [
            ProviderAttempt(
                label="腾讯财经指数K线",
                loader=lambda: _require_index_kline_frame(
                    "腾讯财经指数K线",
                    call_blocking(
                        _get_tencent_provider().fetch_index_kline,
                        symbol,
                        start_date,
                        end_date,
                        semaphore=tencent_semaphore,
                    ),
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                ),
                on_error=f"腾讯财经指数K线不可用，尝试 TDX 指数K线: symbol={symbol}",
            ),
            ProviderAttempt(
                label="TDX 指数K线",
                loader=lambda: _require_index_kline_frame(
                    "TDX 指数K线",
                    call_blocking(
                        _get_tdxhub_provider().fetch_index_kline,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        semaphore=tdx_semaphore,
                    ),
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                ),
                on_error=f"TDX 指数K线不可用，尝试 Akshare 新浪指数K线: symbol={symbol}",
            ),
            ProviderAttempt(
                label="Akshare 新浪指数K线",
                loader=lambda: _require_index_kline_frame(
                    "Akshare 新浪指数K线",
                    _load_and_filter(
                        _get_akshare_provider().fetch_index_kline_sina,
                        symbol,
                        start_date,
                        end_date,
                    ),
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                ),
                on_error=f"Akshare 新浪指数K线不可用，尝试东方财富 fallback: symbol={symbol}",
            ),
            ProviderAttempt(
                label="东方财富指数K线直连（fallback）",
                loader=lambda: _require_index_kline_frame(
                    "东方财富指数K线直连",
                    call_blocking(
                        _get_eastmoney_provider().fetch_index_kline,
                        symbol,
                        period,
                        start_date,
                        end_date,
                        semaphore=eastmoney_semaphore,
                    ),
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                ),
                on_error=f"东方财富指数K线直连 fallback 不可用，尝试 Akshare 东方财富最终 fallback: symbol={symbol}",
            ),
            ProviderAttempt(
                label="Akshare 东方财富指数K线（fallback）",
                loader=lambda: _require_index_kline_frame(
                    "Akshare 东方财富指数K线",
                    call_blocking(
                        _get_akshare_provider().fetch_index_kline,
                        symbol=symbol,
                        period=period,
                        start_date=start_date,
                        end_date=end_date,
                        semaphore=akshare_semaphore,
                    ),
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                ),
                on_error=f"Akshare 东方财富指数K线最终 fallback 不可用: symbol={symbol}",
            ),
        ]

    # ── 非日线（weekly / monthly / annual）：取日线后本地聚合 ──────────
    period_label = {"weekly": "周", "monthly": "月", "annual": "年"}.get(period, period)

    async def _load_daily_then_resample(
        source_label: str,
        raw_loader: Awaitable[pd.DataFrame],
    ) -> pd.DataFrame:
        """取日线 frame 后聚合为目标周期，并校验结果。"""
        daily_frame = await raw_loader
        if daily_frame.empty:
            raise ValueError(f"{source_label} 未返回有效日线数据")
        resampled = await asyncio.to_thread(_resample_adjusted_daily_frame, daily_frame, period)
        if resampled.empty:
            raise ValueError(f"{source_label} 聚合后为空")
        return validate_kline_frame(
            source_label,
            resampled,
            start_date=start_date,
            end_date=end_date,
            period=period,
            require_coverage=True,
        )

    return [
        ProviderAttempt(
            label=f"腾讯财经日线聚合指数{period_label}K线",
            loader=lambda: _load_daily_then_resample(
                f"腾讯财经日线聚合指数{period_label}K线",
                call_blocking(
                    _get_tencent_provider().fetch_index_kline,
                    symbol,
                    start_date,
                    end_date,
                    semaphore=tencent_semaphore,
                ),
            ),
            on_error=f"腾讯财经日线聚合指数{period_label}K线不可用，尝试 TDX: symbol={symbol}",
        ),
        ProviderAttempt(
            label=f"TDX 日线聚合指数{period_label}K线",
            loader=lambda: _load_daily_then_resample(
                f"TDX 日线聚合指数{period_label}K线",
                call_blocking(
                    _get_tdxhub_provider().fetch_index_kline,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    semaphore=tdx_semaphore,
                ),
            ),
            on_error=f"TDX 日线聚合指数{period_label}K线不可用，尝试 Akshare 新浪: symbol={symbol}",
        ),
        ProviderAttempt(
            label=f"Akshare 新浪日线聚合指数{period_label}K线",
            loader=lambda: _load_daily_then_resample(
                f"Akshare 新浪日线聚合指数{period_label}K线",
                _load_and_filter(
                    _get_akshare_provider().fetch_index_kline_sina,
                    symbol,
                    start_date,
                    end_date,
                ),
            ),
            on_error=f"Akshare 新浪日线聚合指数{period_label}K线不可用，尝试东财原生: symbol={symbol}",
        ),
        ProviderAttempt(
            label=f"东方财富指数{period_label}K线直连（fallback）",
            loader=lambda: _require_index_kline_frame(
                f"东方财富指数{period_label}K线直连",
                call_blocking(
                    _get_eastmoney_provider().fetch_index_kline,
                    symbol,
                    period,
                    start_date,
                    end_date,
                    semaphore=eastmoney_semaphore,
                ),
                period=period,
                start_date=start_date,
                end_date=end_date,
            ),
            on_error=f"东方财富指数{period_label}K线直连 fallback 不可用: symbol={symbol}",
        ),
        ProviderAttempt(
            label=f"Akshare 东方财富指数{period_label}K线（fallback）",
            loader=lambda: _require_index_kline_frame(
                f"Akshare 东方财富指数{period_label}K线",
                call_blocking(
                    _get_akshare_provider().fetch_index_kline,
                    symbol=symbol,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    semaphore=akshare_semaphore,
                ),
                period=period,
                start_date=start_date,
                end_date=end_date,
            ),
            on_error=f"Akshare 东方财富指数{period_label}K线最终 fallback 不可用: symbol={symbol}",
        ),
    ]


def _to_kline_data(symbol: str, period: str, df: pd.DataFrame) -> KlineData:
    """将 DataFrame 转换为标准化的 KlineData 模型。

    Param:
        symbol: 指数代码
        period: K 线周期
        df: 包含 OHLCV 字段的 DataFrame
    Return:
        填充了 KlineItem 列表的 KlineData 对象
    """
    items: list[KlineItem] = []
    for _, row in df.iterrows():
        parsed_date = pd.to_datetime(row.get("日期", row.get("date", "")), errors="coerce")
        if pd.isna(parsed_date):
            continue
        items.append(
            KlineItem(
                code=symbol,
                date=parsed_date.strftime("%Y-%m-%d"),
                open=float(row.get("开盘", row.get("open", 0)) or 0),
                close=float(row.get("收盘", row.get("close", 0)) or 0),
                high=float(row.get("最高", row.get("high", 0)) or 0),
                low=float(row.get("最低", row.get("low", 0)) or 0),
                volume=safe_float(row.get("成交量", row.get("volume"))) or 0,
                amount=safe_float(row.get("成交额", row.get("amount"))) or 0,
                amplitude=safe_float(row.get("振幅", row.get("amplitude"))),
                turnover_pct=safe_float(row.get("换手率", row.get("turnover_pct"))),
                change_pct=safe_float(row.get("涨跌幅", row.get("change_pct"))),
                pre_close=safe_float(row.get("昨收", row.get("pre_close"))),
            )
        )
    return KlineData(code=symbol, period=period, adjust="", items=items)


async def _load_index_kline(symbol: str, period: str, start_date: str, end_date: str) -> KlineData:
    """通过指数数据源回退链加载并标准化 K 线。"""
    try:
        frame, report = await BaseProviderChain(
            _build_index_kline_source_attempts(symbol, period, start_date, end_date),
            operation="index_kline",
        ).run_with_report()
    except Exception as error:
        raise UpstreamUnavailableError(f"指数 {symbol} 行情上游暂时不可用") from error
    result = _to_kline_data(symbol, period, frame).model_copy(
        update={"source": report.selected_label},
    )
    logger.info(
        "指数K线获取成功: symbol=%s, source=%s, items=%s",
        symbol,
        result.source,
        len(result.items),
    )
    return result


async def get_index_kline(symbol: str, period: str = "daily", start_date: str = "", end_date: str = "") -> KlineData:
    """获取指数 K 线数据，支持多数据源回退和交易时段感知缓存。

    Param:
        symbol: 指数代码
        period: K 线周期，默认 daily
        start_date: 起始日期，留空默认一年前
        end_date: 结束日期，留空默认当天
    Return:
        指数 K 线数据 KlineData
    """
    if not end_date:
        end_date = cache_date()
    if not start_date:
        start_date = one_year_ago_date()

    parsed_start_date = parse_market_date(start_date, "start_date")
    parsed_end_date = parse_market_date(end_date, "end_date")
    if parsed_start_date > parsed_end_date:
        raise ValueError("start_date 不能晚于 end_date")
    parsed_start_date = _clamp_start_date(parsed_start_date, parsed_end_date)

    local = None
    if period == "daily":
        local = await load_local_daily_kline(
            market="cn",
            instrument_type="index",
            code=normalize_index_code(symbol),
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )
        if parsed_start_date == parsed_end_date and local is not None:
            return local

    upstream_windows: list[tuple[date, date]] = [(parsed_start_date, parsed_end_date)]
    if period == "daily" and local is not None:
        windows = _upstream_windows(local, parsed_start_date, parsed_end_date)
        if windows is None:
            return local
        if windows:
            upstream_windows = windows

    policy = await resolve_market_data_cache_policy(period, parsed_end_date)
    cache_key_parts: list[object] = [
        "market_index_kline",
        symbol,
        period,
        parsed_start_date.isoformat(),
        parsed_end_date.isoformat(),
    ]
    if upstream_windows != [(parsed_start_date, parsed_end_date)]:
        cache_key_parts.append(
            "upstream-" + ",".join(f"{start.isoformat()}_{end.isoformat()}" for start, end in upstream_windows)
        )
    cache_key = dated_cache_key_no_day(*cache_key_parts)
    # 与个股 K 线一致：交易时段内用短 TTL 替代“完全不缓存”，合并重复回源。
    write_ttl = (
        LIVE_MARKET_DATA_CACHE_TTL_SECONDS
        if policy.is_live
        else policy.ttl_seconds if policy.write_cache else None
    )
    if policy.read_cache or policy.is_live:
        cached = series_cache.get(cache_key)
        if cached is not None:
            return merge_local_daily_kline(cached, local)

    async def load_and_cache() -> KlineData:
        try:
            parts: list[KlineData] = []
            for window_start, window_end in upstream_windows:
                parts.append(
                    await _load_index_kline(
                        symbol,
                        period,
                        window_start.isoformat(),
                        window_end.isoformat(),
                    )
                )
            result = _merge_upstream_parts(parts)
        except Exception:
            if local is not None and local.items:
                logger.info(
                    "指数K线缺口补采失败，回退本地历史: symbol=%s windows=%s",
                    symbol,
                    upstream_windows,
                )
                return local
            raise
        result = merge_local_daily_kline(result, local)
        if write_ttl is not None:
            series_cache.set(cache_key, result, ttl=write_ttl)
        return result

    return await _index_kline_singleflight.do(cache_key, load_and_cache)

