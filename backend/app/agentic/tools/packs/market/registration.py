"""市场数据 Tool 注册。"""

from __future__ import annotations

from typing import Any

from app.agentic.catalog import registry
from app.agentic.tools.application import get_application_tool_handlers
from app.agentic.tools.contracts import Tool, ToolPolicy

_MARKET_REALTIME_POLICY = ToolPolicy(cache_ttl_seconds=15, freshness="realtime")
_HOT_RANK_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=30, freshness="realtime")
_MARKET_DAILY_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=300, freshness="daily")
_REVIEW_POLICY = ToolPolicy(
    cost="high",
    cache_ttl_seconds=300,
    freshness="daily",
    scope="user",
    timeout_seconds=180,
    max_parallel_calls=2,
)
_MACRO_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=3600, freshness="daily")


async def _get_market_overview() -> Any:
    """获取大盘概览，并行获取主要指数行情和两市成交额。"""
    return await get_application_tool_handlers().get_market_overview()


async def _get_hot_rank(type: str = "stocks") -> Any:
    """获取热门排名数据，根据 type 返回热门概念/行业/股票。

    Param:
        type: 热门类型，concepts=热门概念，industries=热门行业，其他=热门股票
    Return:
        对应类型的热门排名数据
    """
    return await get_application_tool_handlers().get_hot_rank(type=type)


async def _get_dragon_tiger(date: str | None = None) -> Any:
    """获取指定日期的龙虎榜数据。

    Param:
        date: 日期，格式 YYYY-MM-DD，默认 None 表示当天
    Return:
        龙虎榜列表数据
    """
    return await get_application_tool_handlers().get_dragon_tiger(date=date)


async def _get_daily_review(date: str | None = None, force: bool = False) -> Any:
    """生成每日复盘报告并格式化为 Markdown 文本。

    Param:
        date: 日期，格式 YYYY-MM-DD，默认 None 表示当天
        force: 是否强制重新生成（忽略缓存）
    Return:
        格式化为 Markdown 的复盘报告文本
    """
    result = await get_application_tool_handlers().generate_daily_review(date=date, force=force)

    sections = [f"### {result.title}", "", f"**市场概要**：{result.market_summary}", ""]
    for review in [result.index_review, result.hotspot_review, result.dragon_tiger_review]:
        sections.append(f"### {review.title}")
        sections.append(review.summary)
        for bullet in review.bullets:
            sections.append(f"- {bullet}")
        sections.append("")
    if result.risk_alerts:
        sections.append("### ⚠️ 风险提示")
        for alert in result.risk_alerts:
            sections.append(f"- {alert}")
        sections.append("")
    if result.opportunities:
        sections.append("### 💡 机会展望")
        for opp in result.opportunities:
            sections.append(f"- {opp}")
        sections.append("")
    if result.strategy_notes:
        sections.append("### 📋 策略建议")
        for note in result.strategy_notes:
            sections.append(f"- {note}")
        sections.append("")
    if result.llm_review:
        sections.append("### 🤖 AI 深度分析")
        sections.append(result.llm_review)
    return "\n".join(sections)


async def _get_macro_data() -> Any:
    """获取宏观经济指标汇总：CPI、PPI、PMI 和货币供应量。

    Return:
        包含 cpi/ppi/pmi/money_supply 四个板块的字典
    """
    return await get_application_tool_handlers().get_macro_data()


async def _get_market_mainline() -> Any:
    """获取财联社今日主线机会与风格判断。

    Return:
        主线机会列表（含板块涨跌与龙头股）和风格判断
    """
    return await get_application_tool_handlers().get_market_mainline()


async def _get_industry_rankings(date: str | None = None) -> Any:
    """获取行业板块涨跌与资金排行（含开盘红板块代码）。

    Param:
        date: 日期，格式 YYYY-MM-DD；省略则查询当天
    Return:
        行业板块排行列表（rank/code/name/change_pct/net_inflow 等）
    """
    return await get_application_tool_handlers().get_industry_rankings(date=date)


async def _get_sector_stocks_history(date: str, plate_id: str) -> Any:
    """获取开盘红板块在指定历史日期的成分股。

    Param:
        date: 历史日期，格式 YYYY-MM-DD，必须早于今天
        plate_id: 开盘红板块 ID，如 881169
    Return:
        板块成分股列表（含涨跌幅、主力资金、连板标签）
    """
    return await get_application_tool_handlers().get_sector_stocks_history(
        date=date,
        plate_id=plate_id,
    )


def register_market_tools(target_registry=None):
    """注册市场相关技能：get_market_overview、get_hot_rank、get_dragon_tiger、get_daily_review、get_macro_data、get_market_mainline、get_sector_stocks_history。"""
    target = target_registry or registry
    target.register_tool(Tool(
        name="get_market_overview",
        description="获取大盘概览，包括主要指数（上证、深证、创业板等）实时行情和两市成交额。当用户问'大盘怎么样''指数行情''市场情况'时调用。",
        parameters={"type": "object", "properties": {}},
        policy=_MARKET_REALTIME_POLICY,
        executor=_get_market_overview,
    ))

    target.register_tool(Tool(
        name="get_hot_rank",
        description="获取热门排名数据。当用户问'最近什么火''热门股''热门概念''热门行业'时调用，通过type参数指定查询类型。",
        parameters={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["stocks", "concepts", "industries"],
                    "default": "stocks",
                    "description": "热门类型：stocks=热门股票，concepts=热门概念，industries=热门行业",
                },
            },
        },
        policy=_HOT_RANK_POLICY,
        executor=_get_hot_rank,
    ))

    target.register_tool(Tool(
        name="get_dragon_tiger",
        description="获取龙虎榜数据，查看游资和机构席位动向。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "日期，格式 YYYY-MM-DD；省略则查询当天",
                },
            },
        },
        policy=_MARKET_DAILY_POLICY,
        executor=_get_dragon_tiger,
    ))

    target.register_tool(Tool(
        name="get_daily_review",
        description="生成每日大盘复盘报告，包含指数表现、热点题材、龙虎榜、风险提示、机会展望和策略建议。当用户问'今天大盘怎么样''复盘''市场总结'时调用。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "日期，格式 YYYY-MM-DD；省略则生成当天复盘",
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "忽略缓存强制重新生成；仅当已有复盘过期或内容缺失时使用",
                },
            },
        },
        policy=_REVIEW_POLICY,
        executor=_get_daily_review,
    ))

    target.register_tool(Tool(
        name="get_macro_data",
        description="获取最新常用宏观指标汇总，包括CPI、PPI、PMI和货币供应量M0/M1/M2。指定历史区间、口径或单项查询时使用 iwencai_market_macro。",
        parameters={"type": "object", "properties": {}},
        policy=_MACRO_POLICY,
        executor=_get_macro_data,
    ))

    target.register_tool(Tool(
        name="get_industry_rankings",
        description="获取行业板块涨跌与资金排行，包括排名、板块代码、涨跌幅、成交额和主力净流入。当用户问'哪些板块领涨''板块资金''行业排行'时调用；板块代码可作为 get_sector_stocks_history 的 plate_id 查询成分股。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "日期，格式 YYYY-MM-DD；省略则查询当天",
                },
            },
        },
        policy=_MARKET_DAILY_POLICY,
        executor=_get_industry_rankings,
    ))

    target.register_tool(Tool(
        name="get_market_mainline",
        description="获取财联社今日主线机会与市场风格判断，包括主线题材、持续天数、热度、关联板块涨跌、龙头股和风格解读。当用户问'今天主线''主线机会''什么题材在走''市场风格'时调用。",
        parameters={"type": "object", "properties": {}},
        policy=_MARKET_DAILY_POLICY,
        executor=_get_market_mainline,
    ))

    target.register_tool(Tool(
        name="get_sector_stocks_history",
        description="获取开盘红板块在指定日期的成分股明细。历史日期返回开盘红历史详情；当天使用最近历史交易日的开盘红成分名单，并补充最新价格、涨跌幅、成交额、换手率和流通市值。先用 get_industry_rankings 获取板块代码（code 字段）作为 plate_id。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "查询日期，格式 YYYY-MM-DD，支持当天和历史日期",
                },
                "plate_id": {
                    "type": "string",
                    "description": "开盘红板块 ID，例如 881169",
                },
            },
            "required": ["date", "plate_id"],
        },
        policy=_MARKET_DAILY_POLICY,
        executor=_get_sector_stocks_history,
    ))

    target.register_tool(Tool(
        name="get_commodity_spot_prices",
        description="查询大宗商品期货连续/主力合约最近报价与静态产业映射；旧工具名兼容，不提供现货、基差或企业采购成本（覆盖碳酸锂、工业硅、铜、铝、锌、镍、锡、黄金、白银、螺纹钢、铁矿石、焦炭、原油、甲醇、PTA、纯碱、生猪等）。支持指定商品名称，或省略参数查看全部大宗商品概览。",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "大宗商品名称或关键词，例如：碳酸锂、工业硅、电解铜、螺纹钢、生猪、原油；省略则返回全市场重要大宗商品概览",
                    "default": "",
                },
            },
        },
        policy=ToolPolicy(cache_ttl_seconds=0, freshness="realtime"),
        executor=_get_commodity_spot_prices,
    ))

    target.register_tool(Tool(
        name="get_global_macro_rates",
        description="获取全球宏观利率、中美10年期国债收益率、中美利差、美元指数 (DXY)、离岸人民币 (USD/CNH) 及央行政策利率。当用户问'美债收益率''中美利差''美元指数''全球流动性''汇率'时调用。",
        parameters={"type": "object", "properties": {}},
        policy=_MARKET_REALTIME_POLICY,
        executor=_get_global_macro_rates,
    ))

    target.register_tool(Tool(
        name="get_customs_trade_data",
        description="获取全国近12个月进出口总额、差额、同比。commodity仅筛选静态商品介绍与公司映射，不返回该商品的出口量、金额、均价、目的地或HS编码序列。静态映射不能证明订单或受益。",
        parameters={
            "type": "object",
            "properties": {
                "commodity": {
                    "type": "string",
                    "description": "重点出海或进口商品名称，例如：汽车、锂电池、光伏、芯片、家电、船舶、工程机械、钢材、原油；省略则返回海关宏观进出口总况与核心出海分类概览",
                    "default": "",
                },
            },
        },
        policy=ToolPolicy(cache_ttl_seconds=0, freshness="daily"),
        executor=_get_customs_trade_data,
    ))


async def _get_commodity_spot_prices(symbol: str = "") -> Any:
    """获取大宗商品期货最近报价，不含现货或基差。"""
    from app.financial_data.market.quotes.commodity import get_commodity_spot_prices
    return await get_commodity_spot_prices(symbol=symbol)


async def _get_global_macro_rates() -> Any:
    """获取全球宏观利率、国债收益率与汇率流动性看板。"""
    from app.financial_data.market.quotes.global_macro import get_global_macro_rates
    return await get_global_macro_rates()


async def _get_customs_trade_data(commodity: str = "") -> Any:
    """获取海关进出口贸易与重点出海商品数据。"""
    from app.financial_data.market.quotes.customs import get_customs_trade_data
    return await get_customs_trade_data(commodity=commodity)



