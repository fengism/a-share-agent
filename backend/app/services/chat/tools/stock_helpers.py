from __future__ import annotations

from typing import Any

from app.utils.rate_limiter import call_blocking


async def search_stocks(query: str) -> Any:
    """按代码或名称模糊搜索股票。

    Param:
        query: 搜索关键词（代码或名称）
    Return:
        匹配的股票字典列表
    """
    from app.services.stock.search import search_stocks as _search_stocks
    result = await _search_stocks(query)
    return [item.model_dump() for item in result]


async def get_stock_info(code: str) -> Any:
    """获取股票基本信息。

    Param:
        code: 6位股票代码
    Return:
        股票基本信息字典
    """
    from app.services.stock.basic_info import get_basic_info
    result = await get_basic_info(code)
    return result.model_dump()


async def get_stock_valuation_detail(code: str) -> Any:
    """获取股票详细估值分析。

    Param:
        code: 6位股票代码
    Return:
        详细估值数据字典
    """
    from app.services.screener.percentiles import _compute_percentile
    from app.services.stock.valuation import get_valuation_detail
    result = await get_valuation_detail(code, _compute_percentile)
    return result.model_dump()


async def get_stock_technical_indicators(code: str) -> Any:
    """计算股票技术指标。

    Param:
        code: 6位股票代码
    Return:
        技术指标字典（不含 series）
    """
    from app.services.stock.kline import get_kline
    from app.services.technical.indicators import calculate_all
    kline_data = await get_kline(code)
    indicators = calculate_all(kline_data.items)
    indicators.pop("series", None)
    return indicators


async def get_stock_kline(code: str, period: str = "daily") -> Any:
    """获取股票 K 线数据。

    Param:
        code: 6位股票代码
        period: K线周期，daily/weekly/monthly，默认 daily
    Return:
        K线数据字典
    """
    from app.services.stock.kline import get_kline
    result = await get_kline(code, period=period)
    return result.model_dump()


async def get_stock_financial(code: str, indicator: str = "balance") -> Any:
    """获取股票财务报表数据。

    Param:
        code: 6位股票代码
        indicator: 报表类型，balance/profit/cashflow，默认 balance
    Return:
        财务报表数据
    """
    from app.services.stock.financials import get_financial
    return await get_financial(code, indicator=indicator)


async def get_stock_news(code: str) -> Any:
    """获取股票相关新闻列表。

    Param:
        code: 6位股票代码
    Return:
        新闻项字典列表
    """
    from app.services.analysis.news import get_stock_news as _get_stock_news
    result = await _get_stock_news(code)
    return [item.model_dump() if hasattr(item, "model_dump") else item for item in result]


async def get_stock_sentiment(code: str) -> Any:
    """获取股票情绪数据。

    Param:
        code: 6位股票代码
    Return:
        情绪数据字典
    """
    from app.services.analysis.retail import get_stock_sentiment
    return await get_stock_sentiment(code)


async def screen_stocks(**kwargs) -> Any:
    """按固定维度筛选股票。

    Param:
        **kwargs: 筛选参数，如 pe_min、pe_max、industries、page、page_size 等
    Return:
        筛选结果字典，包含分页信息和股票列表
    """
    from app.models.screener import ScreenerFilter
    from app.services.screener.screening import screen_stocks as _screen_stocks
    filter_data = {k: v for k, v in kwargs.items() if v is not None}
    if "page" not in filter_data:
        filter_data["page"] = 1
    if "page_size" not in filter_data:
        filter_data["page_size"] = 20
    sf = ScreenerFilter(**filter_data)
    result = await _screen_stocks(sf)
    return result.model_dump()


async def get_industries() -> Any:
    """获取所有行业列表。

    Param:
        无
    Return:
        行业列表数据
    """
    from app.services.screener.industry import get_industry_list
    return await get_industry_list()


def _get_iwencai_provider():
    """获取问财数据源 provider 实例，未启用时返回 None。

    Param:
        无
    Return:
        iwencai_provider 实例或 None
    """
    from app.config import get_settings
    from app.services.providers import get_provider
    settings = get_settings()
    if not settings.iwencai_enabled:
        return None
    return get_provider("iwencai")


async def iwencai_search(query: str, channel: str = "report", size: int = 20) -> Any:
    """通过问财搜索研报、公告或新闻。

    Param:
        query: 搜索关键词
        channel: 搜索类型，report/announcement/news，默认 report
        size: 返回条数
    Return:
        搜索结果列表或包含 error 的字典
    """
    size = int(size)
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    if channel == "news":
        result = await call_blocking(iwencai_provider.search_news, query, size)
        return [item.model_dump() for item in result[:size]]
    result = await call_blocking(iwencai_provider.search, query, channel, size)
    return iwencai_provider.dedup_articles(result)[:size]


async def iwencai_query(query: str, limit: int = 30) -> Any:
    """通过问财执行自然语言结构化数据查询。

    Param:
        query: 自然语言查询语句
        limit: 返回条数
    Return:
        查询结果或包含 error 的字典
    """
    limit = int(limit)
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await call_blocking(iwencai_provider.query_stock_data, query, 1, limit)


async def iwencai_select_stock(query: str, limit: int = 20) -> Any:
    """通过问财执行自然语言选股。

    Param:
        query: 自然语言选股条件
        limit: 返回条数
    Return:
        选股结果或包含 error 的字典
    """
    limit = int(limit)
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await call_blocking(iwencai_provider.select_stocks, query, 1, limit)


async def get_stock_risk_data(code: str) -> Any:
    """获取个股风险评估相关数据：资金流向、融资融券、大宗交易、股东户数变化。

    Param:
        code: 6位股票代码
    Return:
        包含 fund_flow、margin_trading、block_trade、holder_change 四个维度的字典
    """
    import asyncio
    from app.utils.rate_limiter import call_blocking

    async def _fetch_all():
        from app.services.providers import get_provider
        provider = get_provider("eastmoney")
        fund_flow = await call_blocking(provider.fetch_stock_fund_flow, code)
        margin = await call_blocking(provider.fetch_margin_trading, code)
        block = await call_blocking(provider.fetch_block_trade, code)
        holder = await call_blocking(provider.fetch_holder_num_change, code)
        return fund_flow, margin, block, holder

    fund_flow, margin, block, holder = await _fetch_all()
    return {
        "fund_flow": fund_flow[-30:] if fund_flow else [],   # 最近30个交易日
        "margin_trading": margin[:10] if margin else [],      # 最近10条
        "block_trade": block[:10] if block else [],           # 最近10条
        "holder_change": holder[:4] if holder else [],        # 最近4期（季度级）
    }


async def iwencai_market_macro(query: str, limit: int = 20) -> Any:
    """通过问财查询宏观经济数据。

    Param:
        query: 自然语言宏观经济查询语句
        limit: 返回条数
    Return:
        宏观数据查询结果或包含 error 的字典
    """
    limit = int(limit)
    iwencai_provider = _get_iwencai_provider()
    if iwencai_provider is None:
        return {"error": "问财数据源未启用，请在设置中开启 iwencai_enabled"}
    return await call_blocking(iwencai_provider.query_market_macro, query, 1, limit)
