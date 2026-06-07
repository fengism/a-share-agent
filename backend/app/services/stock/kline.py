from app.models.stock import KlineData, KlineItem
from app.services.base.provider_chain import BaseProviderChain, ProviderAttempt
from app.services.providers.baidu import baidu_provider as _baidu_provider
from app.services.providers.tdx import tdx_provider
from app.utils.cache import cache, cache_date, dated_cache_key, one_year_ago_date
from app.utils.rate_limiter import call_blocking
from app.utils.singleflight import AsyncSingleFlight
from app.utils.symbol_utils import normalize_code
from app.utils.data_clean import safe_float


_kline_singleflight = AsyncSingleFlight[KlineData]()


def _build_kline_source_attempts(code: str, period: str, start_date: str, end_date: str, adjust: str) -> list[ProviderAttempt]:
    """构造股票 K 线多数据源回退链。

    Param:
        code: 股票代码
        period: K 线周期
        start_date: 起始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
        adjust: 复权类型（qfq/hfq/none）
    Return:
        Provider 尝试列表，按优先级排序
    """
    return [
        ProviderAttempt(
            label="百度股票K线",
            loader=lambda: call_blocking(_baidu_provider.fetch_stock_kline, code=code, start_date=start_date, end_date=end_date),
            on_error=f"百度股票K线不可用，尝试 TDX 股票K线: code={code}",
        ),
        ProviderAttempt(
            label="TDX 股票K线",
            loader=lambda: call_blocking(tdx_provider.fetch_stock_kline, code=code, start_date=start_date, end_date=end_date),
            on_error=f"TDX 股票K线不可用: code={code}",
        ),
    ]

async def _fetch_kline_with_fallback(code: str, period: str, start_date: str, end_date: str, adjust: str):
    """按回退链获取 K 线 DataFrame。

    Param:
        code: 股票代码
        period: K 线周期
        start_date: 起始日期
        end_date: 结束日期
        adjust: 复权类型
    Return:
        K 线 DataFrame
    """
    return await BaseProviderChain(_build_kline_source_attempts(code, period, start_date, end_date, adjust)).run()


async def _load_kline(sym, period: str, start_date: str, end_date: str, adjust: str) -> KlineData:
    """加载 K 线并构造 KlineData，缺失涨跌幅时补算。

    Param:
        sym: 归一化后的代码对象
        period: K 线周期
        start_date: 起始日期
        end_date: 结束日期
        adjust: 复权类型
    Return:
        KlineData 模型对象
    """
    df = await _fetch_kline_with_fallback(sym.raw, period, start_date, end_date, adjust)

    items: list[KlineItem] = []
    for _, row in df.iterrows():
        items.append(
            KlineItem(
                code=sym.raw,
                date=str(row.get("日期", row.get("date", ""))),
                open=safe_float(row.get("开盘", row.get("open"))),
                close=safe_float(row.get("收盘", row.get("close"))),
                high=safe_float(row.get("最高", row.get("high"))),
                low=safe_float(row.get("最低", row.get("low"))),
                volume=safe_float(row.get("成交量", row.get("volume"))),
                amount=safe_float(row.get("成交额", row.get("amount"))),
                amplitude=safe_float(row.get("振幅", row.get("amplitude"))),
                turnover_pct=safe_float(row.get("换手率", row.get("turnover_pct"))),
                change_pct=safe_float(row.get("涨跌幅", row.get("change_pct"))),
                pre_close=safe_float(row.get("昨收", row.get("pre_close"))),
            )
        )

    for i in range(1, len(items)):
        if items[i].change_pct is None and items[i - 1].close not in (None, 0) and items[i].close is not None:
            items[i].change_pct = round((items[i].close - items[i - 1].close) / items[i - 1].close * 100, 2)

    return KlineData(code=sym.raw, period=period, adjust=adjust, items=items)


async def get_kline(
    code: str, period: str = "daily", start_date: str = "", end_date: str = "", adjust: str = "qfq"
) -> KlineData:
    """获取股票 K 线数据，带 single-flight 与 5 分钟缓存。

    Param:
        code: 股票代码
        period: K 线周期，默认 daily
        start_date: 起始日期，留空默认一年前
        end_date: 结束日期，留空默认当天
        adjust: 复权类型，默认 qfq
    Return:
        KlineData 模型对象
    """
    sym = normalize_code(code)
    today = cache_date()
    if not end_date:
        end_date = today
    if not start_date:
        start_date = one_year_ago_date()

    cache_key = dated_cache_key("kline", sym.raw, period, start_date, end_date, adjust)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    async def load_and_cache() -> KlineData:
        """加载 K 线数据并写入缓存。

        Param:
            无
        Return:
            KlineData 模型对象
        """
        result = await _load_kline(sym, period, start_date, end_date, adjust)
        cache.set(cache_key, result, ttl=300)
        return result

    return await _kline_singleflight.do(cache_key, load_and_cache)

if __name__ == "__main__":
    import asyncio

    kline_data = asyncio.run(get_kline("600519", period="daily", start_date="2026-05-01", end_date="2026-05-19", adjust="qfq"))
    print(kline_data)
