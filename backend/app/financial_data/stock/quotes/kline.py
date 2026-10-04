"""个股 K 线服务。"""

import logging
from datetime import date, timedelta

from app.core.cache import cache_date, dated_cache_key_no_day, one_year_ago_date, series_cache
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import SymbolFormats, normalize_code
from app.domain.market import KlineData
from app.financial_data.dates import clamp_kline_history_start_date, parse_market_date
from app.financial_data.market.trading_session import resolve_market_data_cache_policy
from app.financial_data.stock.quotes.historical import (
    HistoricalRequestLimiter,
    get_historical_bars,
)
from app.modules.market_daily.adjustment import load_local_adjusted_daily_kline
from app.modules.market_daily.reader import load_local_daily_kline, merge_local_daily_kline
from app.modules.market_daily.service import is_cn_trading_day

_kline_singleflight = AsyncSingleFlight[KlineData]()
logger = logging.getLogger(__name__)

_clamp_start_date = clamp_kline_history_start_date


def _parse_item_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


_MAX_TRADING_DAY_SCAN = 31


def _has_cn_trading_day(start_date: date, end_date: date) -> bool:
    """判断区间内是否存在 A 股交易日；用内置交易所日历，避免为纯休市区间打上游。"""
    return _trim_to_trading_days(start_date, end_date) is not None


def _trim_to_trading_days(
    start_date: date,
    end_date: date,
) -> tuple[date, date] | None:
    """把区间裁剪到首个/末个 A 股交易日；区间内无交易日时返回 None。

    短区间（<= 31 天，涵盖所有长假）逐日精确裁剪；更长区间只判定是否含交易日，
    避免逐日扫描多年。
    """
    if start_date > end_date:
        return None
    span = (end_date - start_date).days
    if span > _MAX_TRADING_DAY_SCAN:
        probe_end = start_date + timedelta(days=_MAX_TRADING_DAY_SCAN)
        return (start_date, end_date) if _has_trading_day_between(start_date, probe_end) else None
    first_trading: date | None = None
    last_trading: date | None = None
    for offset in range(span + 1):
        day = start_date + timedelta(days=offset)
        if is_cn_trading_day(day):
            if first_trading is None:
                first_trading = day
            last_trading = day
    if first_trading is None or last_trading is None:
        return None
    return (first_trading, last_trading)


def _has_trading_day_between(start_date: date, end_date: date) -> bool:
    for offset in range((end_date - start_date).days + 1):
        if is_cn_trading_day(start_date + timedelta(days=offset)):
            return True
    return False


def _upstream_windows(
    local: KlineData | None,
    start_date: date,
    end_date: date,
) -> list[tuple[date, date]] | None:
    """计算本地未覆盖、需要走上游的区间列表。

    - 返回 None：本地已完整覆盖（或缺口区间内无交易日），无需访问上游；
    - 返回空列表：本地完全没有数据，由调用方回退整段上游查询；
    - 其余情况返回需要补采的头部/尾部窗口（已裁剪到交易日）。
    """
    if local is None or not local.items:
        return []
    first = _parse_item_date(local.items[0].date)
    last = _parse_item_date(local.items[-1].date)
    if first is None or last is None:
        return [(start_date, end_date)]

    windows: list[tuple[date, date]] = []
    # 头部缺口：起点到本地首根之间若含交易日，说明确有缺失（停牌或本地历史更短）
    if start_date < first:
        head = _trim_to_trading_days(start_date, min(end_date, first - timedelta(days=1)))
        if head is not None:
            windows.append(head)
    # 尾部缺口：本地末根之后（盘中当日/长假后首日），休市区间无需回源
    if end_date > last:
        tail = _trim_to_trading_days(max(start_date, last + timedelta(days=1)), end_date)
        if tail is not None:
            windows.append(tail)
    return windows or None


def _merge_upstream_parts(parts: list[KlineData]) -> KlineData:
    """合并多个上游窗口结果；单段时原样返回，避免额外拷贝。"""
    if len(parts) == 1:
        return parts[0]
    base = parts[0]
    by_date = {item.date: item for item in base.items}
    for part in parts[1:]:
        by_date.update({item.date: item for item in part.items})
    return base.model_copy(
        update={"items": sorted(by_date.values(), key=lambda item: item.date)}
    )


async def _load_kline(
    sym: SymbolFormats,
    period: str,
    start_date: date,
    end_date: date,
    adjust: str,
    require_turnover: bool,
    *,
    max_provider_sources: int | None = None,
    request_limiter: HistoricalRequestLimiter | None = None,
) -> KlineData:
    """通过严格历史行情链加载 K 线并保留数据来源信息。

    Param:
        sym: 归一化后的代码对象
        period: K 线周期
        start_date: 起始日期
        end_date: 结束日期
        adjust: 复权类型
    Return:
        KlineData 模型对象
    """
    historical_kwargs = {
        "period": period,
        "adjust": adjust,
        "require_turnover": require_turnover,
    }
    if max_provider_sources is None and request_limiter is None:
        bars = await get_historical_bars(
            sym.raw,
            start_date,
            end_date,
            **historical_kwargs,
        )
    else:
        bars = await get_historical_bars(
            sym.raw,
            start_date,
            end_date,
            **historical_kwargs,
            max_provider_sources=max_provider_sources,
            request_limiter=request_limiter,
        )
    return KlineData(
        code=bars.code,
        period=bars.period,
        adjust=bars.adjust,
        source=bars.source,
        adjustment_verified=bars.adjustment_verified,
        items=bars.items,
    )


async def get_kline(
    code: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    adjust: str = "qfq",
    *,
    require_turnover: bool = False,
    max_provider_sources: int | None = None,
    request_limiter: HistoricalRequestLimiter | None = None,
) -> KlineData:
    """获取股票 K 线数据，带 single-flight 与交易时段感知缓存。

    Param:
        code: 股票代码
        period: K 线周期，默认 daily
        start_date: 起始日期，留空默认一年前
        end_date: 结束日期，留空默认当天
        adjust: 复权类型，默认 qfq
        require_turnover: 是否要求返回至少一条有效换手率；用于筹码分布等依赖换手率的计算
        max_provider_sources: 最多尝试的数据源数量；仅用于大批量调用抑制 fallback 放大
        request_limiter: 可选的 Provider 级请求节流器
    Return:
        KlineData 模型对象
    """
    sym = normalize_code(code)
    if adjust == "none":
        adjust = ""
    today = cache_date()
    if not end_date:
        end_date = today
    if not start_date:
        start_date = one_year_ago_date()

    parsed_start_date = parse_market_date(start_date, "start_date")
    parsed_end_date = parse_market_date(end_date, "end_date")
    if parsed_start_date > parsed_end_date:
        raise ValueError("start_date 不能晚于 end_date")
    parsed_start_date = _clamp_start_date(parsed_start_date, parsed_end_date)

    local = None
    if period == "daily" and adjust in {"qfq", "hfq"}:
        local = await load_local_adjusted_daily_kline(
            sym.raw, parsed_start_date, parsed_end_date, adjust
        )
    elif period == "daily" and adjust == "":
        local = await load_local_daily_kline(
            market="cn",
            instrument_type="stock",
            code=sym.raw,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )

    local_has_turnover = not require_turnover or (
        local is not None
        and bool(local.items)
        and all(item.turnover_pct is not None for item in local.items)
    )

    if parsed_start_date == parsed_end_date and local is not None and local_has_turnover:
        return local

    # 本地已完整覆盖时直接返回，不再为同一段历史访问上游（10 年区间尤其明显）。
    # require_turnover 且本地无有效换手率时，仍走完整回源路径。
    upstream_windows: list[tuple[date, date]] = [(parsed_start_date, parsed_end_date)]
    if local is not None and local_has_turnover:
        windows = _upstream_windows(local, parsed_start_date, parsed_end_date)
        if windows is None:
            return local
        if windows:
            upstream_windows = windows

    policy = await resolve_market_data_cache_policy(period, parsed_end_date)
    cache_key_parts: list[object] = [
        "kline",
        sym.raw,
        period,
        parsed_start_date.isoformat(),
        parsed_end_date.isoformat(),
        adjust,
    ]
    if upstream_windows != [(parsed_start_date, parsed_end_date)]:
        cache_key_parts.append(
            "upstream-" + ",".join(f"{start.isoformat()}_{end.isoformat()}" for start, end in upstream_windows)
        )
    if max_provider_sources is not None:
        cache_key_parts.append(f"providers-{max_provider_sources}")
    cache_key_parts.append("turnover-required" if require_turnover else "turnover-optional")
    cache_key = dated_cache_key_no_day(*cache_key_parts)
    if policy.read_cache:
        cached = series_cache.get(cache_key)
        if cached is not None:
            return merge_local_daily_kline(cached, local)

    async def load_and_cache() -> KlineData:
        """加载 K 线数据并写入缓存。

        Param:
            无
        Return:
            KlineData 模型对象
        """
        try:
            parts: list[KlineData] = []
            for window_start, window_end in upstream_windows:
                if max_provider_sources is None and request_limiter is None:
                    parts.append(
                        await _load_kline(
                            sym,
                            period,
                            window_start,
                            window_end,
                            adjust,
                            require_turnover,
                        )
                    )
                else:
                    parts.append(
                        await _load_kline(
                            sym,
                            period,
                            window_start,
                            window_end,
                            adjust,
                            require_turnover,
                            max_provider_sources=max_provider_sources,
                            request_limiter=request_limiter,
                        )
                    )
            result = _merge_upstream_parts(parts)
        except Exception:
            # 缺口补采失败不应拖累本地已有历史：非交易日/上游异常时直接用本地数据返回
            if local is not None and local.items:
                logger.info(
                    "K线缺口补采失败，回退本地历史: code=%s windows=%s",
                    sym.raw,
                    upstream_windows,
                )
                return local
            raise
        result = merge_local_daily_kline(result, local)
        if policy.write_cache and policy.ttl_seconds is not None:
            series_cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _kline_singleflight.do(cache_key, load_and_cache)

