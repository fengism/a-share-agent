"""股票 Tool 执行器使用的领域适配函数。"""

from __future__ import annotations

from typing import Any

from app.agentic.tools.application import get_application_tool_handlers


async def iwencai_search(query: str, channel: str = "report", size: int = 20) -> Any:
    return await get_application_tool_handlers().iwencai_search(query, channel=channel, size=size)


async def iwencai_query(query: str, limit: int = 30) -> Any:
    return await get_application_tool_handlers().iwencai_query(query, limit=limit)


async def iwencai_select_stock(query: str, limit: int = 20) -> Any:
    return await get_application_tool_handlers().iwencai_select_stock(query, limit=limit)


async def iwencai_market_macro(query: str, limit: int = 20) -> Any:
    return await get_application_tool_handlers().iwencai_market_macro(query, limit=limit)

async def search_stocks(query: str) -> Any:
    """按代码或名称模糊搜索股票。

    Param:
        query: 搜索关键词（代码或名称）
    Return:
        匹配的股票字典列表
    """
    return await get_application_tool_handlers().search_stocks(query)


async def get_stock_info(code: str) -> Any:
    """获取股票基本信息。

    Param:
        code: 6位股票代码
    Return:
        股票基本信息字典
    """
    return await get_application_tool_handlers().get_stock_info(code)


async def get_stock_valuation_detail(code: str) -> Any:
    """获取股票详细估值分析。

    Param:
        code: 6位股票代码
    Return:
        详细估值数据字典
    """
    return await get_application_tool_handlers().get_stock_valuation_detail(code)


async def get_stock_technical_indicators(code: str, period: str = "daily") -> Any:
    """计算股票技术指标。

    Param:
        code: 6位股票代码
        period: K线周期，daily/weekly/monthly/annual，默认 daily
    Return:
        技术指标字典（不含 series）
    """
    return await get_application_tool_handlers().get_stock_technical_indicators(code, period=period)


async def get_stock_kline(code: str, period: str = "daily") -> Any:
    """获取股票 K 线数据。

    Param:
        code: 6位股票代码
        period: K线周期，daily/weekly/monthly，默认 daily
    Return:
        K线数据字典
    """
    return await get_application_tool_handlers().get_stock_kline(code, period=period)


async def get_stock_financial(code: str, indicator: str = "balance") -> Any:
    """获取股票财务报表数据。

    Param:
        code: 6位股票代码
        indicator: 报表类型，balance/profit/cashflow，默认 balance
    Return:
        财务报表数据
    """
    return await get_application_tool_handlers().get_stock_financial(code, indicator=indicator)


async def get_stock_financial_metrics(code: str) -> Any:
    """获取股票关键财务指标汇总。

    Param:
        code: 6位股票代码
    Return:
        FinancialMetrics 模型对象
    """
    return await get_application_tool_handlers().get_stock_financial_metrics(code)


async def get_stock_revenue_breakdown(code: str) -> Any:
    """获取股票分产品、业务和地区的营收与毛利构成。"""
    return await get_application_tool_handlers().get_stock_revenue_breakdown(code)


async def get_stock_news(code: str) -> Any:
    """获取股票相关新闻列表。

    Param:
        code: 6位股票代码
    Return:
        新闻项字典列表
    """
    return await get_application_tool_handlers().get_stock_news(code)


async def get_stock_sentiment(code: str) -> Any:
    """获取股票情绪数据。

    Param:
        code: 6位股票代码
    Return:
        情绪数据字典
    """
    return await get_application_tool_handlers().get_stock_sentiment(code)


async def screen_stocks(
    pe_min: float | None = None,
    pe_max: float | None = None,
    pb_min: float | None = None,
    pb_max: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    market_cap_min: float | None = None,
    market_cap_max: float | None = None,
    change_pct_min: float | None = None,
    change_pct_max: float | None = None,
    turnover_pct_min: float | None = None,
    turnover_pct_max: float | None = None,
    industries: list[str] | None = None,
    concepts: list[str] | None = None,
    markets: list[str] | None = None,
    exclude_st: bool = False,
    min_listing_days: int | None = None,
    min_amount_yi: float | None = None,
    sort_by: str = "market_cap",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> Any:
    """按固定维度筛选股票。

    参数必须显式声明：Tool 的 Schema 与 executor 签名要能互相校验（见
    validate_executor_contract），收成 **kwargs 就没法发现「下游支持但 Schema
    没声明」的漏参——page/page_size 曾经正是这样漏掉的。
    Return:
        筛选结果字典，包含分页信息和股票列表
    """
    filters: dict[str, Any] = {
        "pe_min": pe_min,
        "pe_max": pe_max,
        "pb_min": pb_min,
        "pb_max": pb_max,
        "price_min": price_min,
        "price_max": price_max,
        "market_cap_min": market_cap_min,
        "market_cap_max": market_cap_max,
        "change_pct_min": change_pct_min,
        "change_pct_max": change_pct_max,
        "turnover_pct_min": turnover_pct_min,
        "turnover_pct_max": turnover_pct_max,
        "industries": industries,
        "concepts": concepts,
        "markets": markets,
        "exclude_st": exclude_st,
        "min_listing_days": min_listing_days,
        "min_amount_yi": min_amount_yi,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "page": page,
        "page_size": page_size,
    }
    return await get_application_tool_handlers().screen_stocks(
        **{key: value for key, value in filters.items() if value is not None}
    )


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
    return await get_application_tool_handlers().get_stock_risk_data(code)


async def get_restricted_shares_lift(code: str) -> Any:
    """获取个股限售解禁日历与抛压监测数据。"""
    from app.financial_data.stock.insights.restricted import get_restricted_shares_lift as _get_lift
    return await _get_lift(code=code)


async def get_interactive_qa(code: str, keyword: str = "", limit: int = 15) -> Any:
    """获取交易所互动平台董秘官方问答。"""
    from app.financial_data.stock.insights.interactive_qa import get_interactive_qa as _get_qa
    return await _get_qa(code=code, keyword=keyword, limit=limit)



async def get_stock_documents(
    code: str,
    kind: str = "all",
    start_date: str = "",
    end_date: str = "",
    keyword: str = "",
    page: int = 1,
    limit: int = 20,
) -> Any:
    """定位公告/定期报告/研报目录。显式签名，供 Tool 的 Schema 反向校验使用。"""
    return await get_application_tool_handlers().get_stock_documents(
        code=code,
        kind=kind,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        page=page,
        limit=limit,
    )
