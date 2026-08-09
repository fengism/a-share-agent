"""股票 Tool 执行器使用的领域适配函数。"""

from __future__ import annotations

from typing import Any

from app.agentic.tools.application import get_application_tool_handlers
from app.market_data import public as market_data


async def iwencai_search(query: str, channel: str = "report", size: int = 20) -> Any:
    return await market_data.iwencai_search(query, channel=channel, size=size)


async def iwencai_query(query: str, limit: int = 30) -> Any:
    return await market_data.iwencai_query(query, limit=limit)


async def iwencai_select_stock(query: str, limit: int = 20) -> Any:
    return await market_data.iwencai_select_stock(query, limit=limit)


async def iwencai_market_macro(query: str, limit: int = 20) -> Any:
    return await market_data.iwencai_market_macro(query, limit=limit)



async def search_stocks(query: str) -> Any:
    """按代码或名称模糊搜索股票。

    Param:
        query: 搜索关键词（代码或名称）
    Return:
        匹配的股票字典列表
    """
    from app.market_data.stock.public import search_stocks as _search_stocks
    result = await _search_stocks(query)
    return [item.model_dump() for item in result]


async def get_stock_info(code: str) -> Any:
    """获取股票基本信息。

    Param:
        code: 6位股票代码
    Return:
        股票基本信息字典
    """
    from app.market_data.stock.public import get_basic_info
    result = await get_basic_info(code)
    return result.model_dump()


async def get_stock_valuation_detail(code: str) -> Any:
    """获取股票详细估值分析。

    Param:
        code: 6位股票代码
    Return:
        详细估值数据字典
    """
    from app.market_data.stock.public import compute_percentile, get_valuation_detail
    result = await get_valuation_detail(code, compute_percentile)
    return result.model_dump()


async def get_stock_technical_indicators(code: str) -> Any:
    """计算股票技术指标。

    Param:
        code: 6位股票代码
    Return:
        技术指标字典（不含 series）
    """
    from app.market_data.stock.public import get_kline, technical
    kline_data = await get_kline(code)
    indicators = technical.calculate_all(kline_data.items)
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
    from app.market_data.stock.public import get_kline
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
    from app.market_data.stock.public import get_financial
    return await get_financial(code, indicator=indicator)


async def get_stock_financial_metrics(code: str) -> Any:
    """获取股票关键财务指标汇总。

    Param:
        code: 6位股票代码
    Return:
        FinancialMetrics 模型对象
    """
    from app.market_data.stock.public import get_financial_metrics
    result = await get_financial_metrics(code)
    return result.model_dump()


async def get_stock_news(code: str) -> Any:
    """获取股票相关新闻列表。

    Param:
        code: 6位股票代码
    Return:
        新闻项字典列表
    """
    from app.market_data.stock.public import get_stock_news as _get_stock_news
    result = await _get_stock_news(code)
    return [item.model_dump() if hasattr(item, "model_dump") else item for item in result]


async def get_stock_sentiment(code: str) -> Any:
    """获取股票情绪数据。

    Param:
        code: 6位股票代码
    Return:
        情绪数据字典
    """
    from app.market_data.stock.public import get_stock_sentiment
    return await get_stock_sentiment(code)


async def screen_stocks(**kwargs) -> Any:
    """按固定维度筛选股票。

    Param:
        **kwargs: 筛选参数，如 pe_min、pe_max、industries、page、page_size 等
    Return:
        筛选结果字典，包含分页信息和股票列表
    """
    return await get_application_tool_handlers().screen_stocks(**kwargs)


async def get_industries() -> Any:
    """获取所有行业列表。

    Param:
        无
    Return:
        行业列表数据
    """
    return await get_application_tool_handlers().get_industries()


async def get_stock_risk_data(code: str) -> Any:
    """获取个股风险评估相关数据：资金流向、融资融券、大宗交易、股东户数变化。

    Param:
        code: 6位股票代码
    Return:
        包含 fund_flow、margin_trading、block_trade、holder_change 四个维度的字典
    """
    from app.market_data.stock.public import get_stock_risk_data as _get_stock_risk_data

    return await _get_stock_risk_data(code)
