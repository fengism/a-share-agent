"""个股 K 线服务。"""

from datetime import date

from app.core.cache import cache_date, dated_cache_key_no_day, one_year_ago_date, series_cache
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.market import SymbolFormats, normalize_code
from app.domain.market import KlineData
from app.financial_data.dates import parse_market_date
from app.financial_data.market.trading_session import resolve_market_data_cache_policy
from app.financial_data.stock.quotes.historical import (
    HistoricalRequestLimiter,
    get_historical_bars,
)
from app.modules.market_daily.adjustment import load_local_adjusted_daily_kline
from app.modules.market_daily.reader import load_local_daily_kline, merge_local_daily_kline

_kline_singleflight = AsyncSingleFlight[KlineData]()


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
    today = cache_date()
    if not end_date:
        end_date = today
    if not start_date:
        start_date = one_year_ago_date()

    parsed_start_date = parse_market_date(start_date, "start_date")
    parsed_end_date = parse_market_date(end_date, "end_date")
    if parsed_start_date > parsed_end_date:
        raise ValueError("start_date 不能晚于 end_date")

    local = None
    if period == "daily" and adjust in {"qfq", "hfq"}:
        local = await load_local_adjusted_daily_kline(
            sym.raw, parsed_start_date, parsed_end_date, adjust
        )
        if parsed_start_date == parsed_end_date and local is not None and not require_turnover:
            return local
    if period == "daily" and adjust == "":
        local = await load_local_daily_kline(
            market="cn",
            instrument_type="stock",
            code=sym.raw,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )
        if parsed_start_date == parsed_end_date and local is not None and not require_turnover:
            return local

    policy = await resolve_market_data_cache_policy(period, parsed_end_date)
    cache_key_parts: list[object] = [
        "kline",
        sym.raw,
        period,
        parsed_start_date.isoformat(),
        parsed_end_date.isoformat(),
        adjust,
    ]
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
        if max_provider_sources is None and request_limiter is None:
            result = await _load_kline(
                sym,
                period,
                parsed_start_date,
                parsed_end_date,
                adjust,
                require_turnover,
            )
        else:
            result = await _load_kline(
                sym,
                period,
                parsed_start_date,
                parsed_end_date,
                adjust,
                require_turnover,
                max_provider_sources=max_provider_sources,
                request_limiter=request_limiter,
            )
        result = merge_local_daily_kline(result, local)
        if policy.write_cache and policy.ttl_seconds is not None:
            series_cache.set(cache_key, result, ttl=policy.ttl_seconds)
        return result

    return await _kline_singleflight.do(cache_key, load_and_cache)
