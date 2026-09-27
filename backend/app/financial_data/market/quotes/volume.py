import asyncio
import logging
from datetime import date, timedelta

from app.core.cache import cache_date, dated_cache_key_no_day, one_year_ago_date
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, ths_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.domain.market import MarketVolume
from app.financial_data.dates import parse_market_date
from app.financial_data.market.quotes.index_kline import get_index_kline
from app.financial_data.market.quotes.schemas import MarketVolumeResponse, MarketVolumeSeriesItem
from app.financial_data.market.quotes.sources import INDEX_KLINE_SOURCE_APIS
from app.financial_data.market.trading_session import resolve_market_data_cache_policy
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

# 上证指数 + 深证成指
_INDEX_SYMBOLS = ("000001", "399001")
_INDEX_MARKETS = {"000001": "shanghai", "399001": "shenzhen"}
_market_volume_singleflight: AsyncSingleFlight[MarketVolumeResponse] = AsyncSingleFlight()


async def _load_market_volume(
    start_date: str,
    end_date: str,
    cache_key: str,
    cache_ttl: int | None,
) -> MarketVolumeResponse:
    kline_results = await asyncio.gather(
        *[
            get_index_kline(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)
            for symbol in _INDEX_SYMBOLS
        ],
        return_exceptions=True,
    )

    aggregated: dict[str, MarketVolumeSeriesItem] = {}
    unavailable_markets = []
    market_sources = {}
    source_apis = {}
    for symbol, kline_result in zip(_INDEX_SYMBOLS, kline_results, strict=True):
        market = _INDEX_MARKETS[symbol]
        if isinstance(kline_result, Exception):
            unavailable_markets.append(market)
            logger.warning("%s 指数K线获取失败，跳过: %s", market, kline_result)
            continue
        if kline_result.source:
            market_sources[market] = kline_result.source
            source_api = INDEX_KLINE_SOURCE_APIS.get(kline_result.source)
            if source_api:
                source_apis[market] = source_api
        for item in kline_result.items:
            raw = item.date.replace("-", "")
            date_str = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) == 8 else raw
            point = aggregated.setdefault(date_str, MarketVolumeSeriesItem(date=date_str))
            point.volume += item.volume or 0.0
            point.amount += item.amount or 0.0

    result = MarketVolumeResponse(
        items=sorted(aggregated.values(), key=lambda item: item.date),
        partial=bool(unavailable_markets),
        unavailable_markets=unavailable_markets,
        market_sources=market_sources,
        source_apis=source_apis,
    )
    if cache_ttl is not None:
        cache.set(cache_key, result, ttl=min(cache_ttl, 30) if result.partial else cache_ttl)
    return result


async def get_market_volume(start_date: str = "", end_date: str = "") -> MarketVolumeResponse:
    """获取沪深两市合计成交量，并显式标记缺失市场。

    通过 get_index_kline 分别获取上证指数和深证成指的日K数据，
    按日期聚合两市的成交量和成交额总和。

    Param:
        start_date: 起始日期，留空默认一年前
        end_date: 结束日期，留空默认当天
    Return:
        MarketVolumeResponse 模型
    """
    if not end_date:
        end_date = cache_date()
    if not start_date:
        start_date = one_year_ago_date()

    parsed_end_date = parse_market_date(end_date, "end_date")
    policy = await resolve_market_data_cache_policy("daily", parsed_end_date)
    cache_key = dated_cache_key_no_day("market_volume", start_date, end_date)
    if policy.read_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return MarketVolumeResponse.model_validate(cached)
    return await _market_volume_singleflight.do(
        cache_key,
        lambda: _load_market_volume(
            start_date,
            end_date,
            cache_key,
            policy.ttl_seconds if policy.write_cache else None,
        ),
    )


async def get_realtime_market_volume() -> MarketVolume:
    """获取同花顺市场成交额实时数据。

    Param:
        无
    Return:
        MarketVolume 模型对象
    """
    return await provider_gateway.call(
        "ths",
        "market_volume",
        lambda: call_blocking(
            get_provider("ths").fetch_market_volume,
            semaphore=ths_semaphore,
        ),
    )


async def get_market_volume_stats(
    target_date: date | None = None,
    *,
    use_realtime: bool = False,
) -> MarketVolume:
    """获取指定日期（或最新交易日）的市场成交额，并计算前一日、20日均值与60日均值。

    结合历史指数日K聚合序列（上证+深证）计算严格的前一日成交额、20日成交额移动平均与60日成交额移动平均。
    若启用实时模式且同花顺分时/日级快照可用，则优先采用实时快照的当日成交额并补充完整均线维度。
    """
    if target_date is None:
        target_date = date.today()

    target_text = target_date.isoformat()
    start_date = (target_date - timedelta(days=160)).isoformat()
    response = await get_market_volume(start_date=start_date, end_date=target_text)
    items = [x for x in response.items if x.date <= target_text]

    cur_item = None
    prev_item = None
    avg20 = None
    avg60 = None
    series_error: str | None = None

    if response.partial:
        # 任一市场 K 线缺失时聚合值只含单边市场，直接采用会输出约一半的失真成交额
        series_error = "市场成交额序列部分市场数据缺失，拒绝以单边市场数据估算"
        logger.warning(
            "%s（缺失市场: %s）", series_error, response.unavailable_markets
        )
    elif items:
        # 优先匹配指定目标日；若目标日非交易日（如周末节假日），自动定位至最近的一个已完成交易日
        matches = [i for i, x in enumerate(items) if x.date == target_text]
        if matches:
            target_idx = matches[0]
        else:
            latest_dt = date.fromisoformat(items[-1].date)
            gap_days = (target_date - latest_dt).days
            if gap_days > 15:
                series_error = (
                    f"截止 {target_text} 缺少近期成交额数据"
                    f"（最新数据 {items[-1].date}，间隔 {gap_days} 天）"
                )
            else:
                target_idx = len(items) - 1
        if series_error is None:
            cur_item = items[target_idx]
            prev_item = items[target_idx - 1] if target_idx > 0 else None
            h20 = items[max(0, target_idx - 19) : target_idx + 1]
            avg20 = sum(x.amount for x in h20) / len(h20) if h20 else None
            h60 = items[max(0, target_idx - 59) : target_idx + 1]
            avg60 = sum(x.amount for x in h60) / len(h60) if h60 else None

    if use_realtime:
        try:
            rt_vol = await get_realtime_market_volume()
            if rt_vol and rt_vol.amount:
                return MarketVolume(
                    date=rt_vol.date or (cur_item.date if cur_item else target_text),
                    amount=rt_vol.amount,
                    amount_before_one_day=rt_vol.amount_before_one_day
                    if rt_vol.amount_before_one_day is not None
                    else (prev_item.amount if prev_item else None),
                    amount_average_20_day=avg20,
                    amount_average_60_day=rt_vol.amount_average_60_day
                    if rt_vol.amount_average_60_day is not None
                    else avg60,
                )
        except Exception as exc:
            logger.warning("实时市场成交额获取失败，降级为历史序列聚合: %s", exc)

    if series_error is not None:
        raise ValueError(series_error)
    if cur_item is None:
        raise ValueError(f"未找到截止 {target_text} 的有效市场成交额数据")

    return MarketVolume(
        date=cur_item.date,
        amount=cur_item.amount,
        amount_before_one_day=prev_item.amount if prev_item else None,
        amount_average_20_day=avg20,
        amount_average_60_day=avg60,
    )
