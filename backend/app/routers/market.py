import logging

from fastapi import APIRouter, HTTPException, Query

from app.services.market.dragon_tiger import (
    get_dragon_tiger_detail as get_dragon_tiger_detail_service,
    get_dragon_tiger_list as get_dragon_tiger_list_service,
)
from app.services.market.hot_rank import (
    get_hot_stocks as get_hot_stocks_service,
    get_ths_hot_concept as get_ths_hot_concept_service,
    get_ths_hot_industry as get_ths_hot_industry_service,
)
from app.services.market.fund_flow import get_hsgt_flow as get_hsgt_flow_service
from app.services.market.index_kline import get_index_kline as get_index_kline_service
from app.services.market.indices import get_indices as get_indices_service
from app.services.market.volume import get_market_volume as get_market_volume_service
from app.services.analysis.news import get_stock_news_categorized as get_stock_news_categorized_service
from app.services.market.news import get_market_feed as get_market_feed_service
from app.services.market.news import get_market_kuaixun as get_market_kuaixun_service
from app.services.market.news import get_market_other_news as get_market_other_news_service
from app.services.market.sector import get_industry_rankings as get_industry_rankings_service
from app.services.market.news_analysis import analyze_market_news as analyze_market_news_service
from app.services.analysis.retail import (
    get_retail_sentiment as get_retail_sentiment_service,
    get_stock_sentiment as get_stock_sentiment_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/indices")
async def get_indices():
    """获取主要大盘指数实时行情。

    Return:
        list[dict] | dict: 上证、深证等核心指数的当前点位与涨跌幅数据。
    """
    logger.info("获取大盘指数")
    try:
        return await get_indices_service()
    except Exception as e:
        logger.error(f"获取大盘指数失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取指数数据失败: {e}")


@router.get("/index-kline")
async def get_index_kline(
    symbol: str = Query(..., description="指数代码，例如 000001"),
    period: str = Query("daily", description="daily / weekly / monthly"),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """获取指数 K 线数据。

    Param:
        symbol: 指数代码（查询参数），例如 000001。
        period: K 线周期（查询参数），daily / weekly / monthly。
        start_date: 起始日期（查询参数），格式 YYYYMMDD，可留空。
        end_date: 结束日期（查询参数），格式 YYYYMMDD，可留空表示至今天。
    Return:
        dict: 指数 K 线时序数据，包含日期、开高低收和成交量。
    """
    logger.info(f"获取指数K线: symbol={symbol}, period={period}, start={start_date}, end={end_date or 'today'}")
    try:
        return await get_index_kline_service(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"获取指数K线失败: symbol={symbol}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取指数K线失败: {e}")


@router.get("/volume")
async def get_volume(start_date: str = Query(""), end_date: str = Query("")):
    """获取大盘成交量历史数据。

    Param:
        start_date: 起始日期（查询参数），格式 YYYYMMDD，可留空。
        end_date: 结束日期（查询参数），格式 YYYYMMDD，可留空。
    Return:
        dict: 大盘成交量、成交额时序数据。
    """
    logger.info(f"获取大盘成交量: start={start_date}, end={end_date}")
    try:
        return await get_market_volume_service(start_date,end_date)
    except Exception as e:
        logger.error(f"获取大盘成交量失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取成交量失败: {e}")


@router.get("/hsgt-flow")
async def get_hsgt_flow():
    """获取沪深股通分钟级资金流向。

    Return:
        dict: 当日沪股通、深股通的分钟级净流入序列。
    """
    logger.info("获取沪深股通分钟流向")
    try:
        return await get_hsgt_flow_service()
    except Exception as e:
        logger.error(f"获取沪深股通分钟流向失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取沪深股通分钟流向失败: {e}")


@router.get("/hsgt-flow/history")
async def get_hsgt_flow_history(days: int = Query(30, description="查询天数")):
    """读取沪深股通历史分钟流向数据。

    Param:
        days: 查询天数（查询参数），默认 30 天。
    Return:
        list[dict]: 每天包含日期、更新时间和分钟级 points 序列。
    """
    logger.info(f"获取沪深股通历史数据: days={days}")
    try:
        from app.db.hsgt_store import query_hsgt_dates, query_hsgt_flow
        dates = query_hsgt_dates(limit=days)
        result = []
        for d in dates:
            date_str = d["date"]
            points = query_hsgt_flow(date_str)
            result.append({
                "date": date_str,
                "updated_at": d.get("updated_at", ""),
                "points": points,
            })
        return result
    except Exception as e:
        logger.error(f"获取沪深股通历史数据失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取沪深股通历史数据失败: {e}")


@router.get("/hot-stocks")
async def get_hot_stocks():
    """获取热门股排名（默认同花顺数据源）。

    Return:
        list[dict]: 热门股排序与对应人气指标。
    """
    logger.info("获取热门股排名")
    try:
        return await get_hot_stocks_service()
    except Exception as e:
        logger.error(f"获取热门股失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取热门股失败: {e}")


@router.get("/hot-rank/ths")
async def get_ths_hot_rank():
    """获取同花顺热股榜单（与 /hot-stocks 等价）。

    Return:
        list[dict]: 同花顺热股榜数据。
    """
    logger.info("获取同花顺热股榜单")
    try:
        return await get_hot_stocks_service()
    except Exception as e:
        logger.error(f"获取同花顺热股榜单失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取同花顺热股榜单失败: {e}")


@router.get("/hot-rank/ths/concept")
async def get_ths_hot_concept():
    """获取同花顺热门概念榜。

    Return:
        list[dict]: 热门概念名称与热度指标。
    """
    logger.info("获取同花顺热门概念")
    try:
        return await get_ths_hot_concept_service()
    except Exception as e:
        logger.error(f"获取同花顺热门概念失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取同花顺热门概念失败: {e}")


@router.get("/hot-rank/ths/industry")
async def get_ths_hot_industry():
    """获取同花顺热门行业榜。

    Return:
        list[dict]: 热门行业名称与对应热度指标。
    """
    logger.info("获取同花顺热门行业")
    try:
        return await get_ths_hot_industry_service()
    except Exception as e:
        logger.error(f"获取同花顺热门行业失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取同花顺热门行业失败: {e}")


@router.get("/dragon-tiger")
async def get_dragon_tiger_list(report_date: str = Query("", description="报告日期 YYYY-MM-DD，默认当天")):
    """获取龙虎榜列表。

    Param:
        report_date: 报告日期（查询参数），格式 YYYY-MM-DD，留空表示当天。
    Return:
        list[dict]: 龙虎榜个股摘要。
    """
    logger.info(f"获取龙虎榜: date={report_date or '今天'}")
    try:
        return await get_dragon_tiger_list_service(report_date or None)
    except Exception as e:
        logger.error(f"获取龙虎榜失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取龙虎榜失败: {e}")


@router.get("/dragon-tiger/{code}")
async def get_dragon_tiger_detail(code: str, report_date: str = Query(..., description="报告日期 YYYY-MM-DD")):
    """获取指定龙虎榜个股的买卖席位明细。

    Param:
        code: 股票代码（路径参数）。
        report_date: 报告日期（查询参数），格式 YYYY-MM-DD。
    Return:
        dict: 买入卖出席位明细及净额。
    """
    logger.info(f"获取龙虎榜明细: code={code}, date={report_date}")
    try:
        return await get_dragon_tiger_detail_service(code, report_date)
    except Exception as e:
        logger.error(f"获取龙虎榜明细失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取龙虎榜明细失败: {e}")


@router.get("/sentiment")
async def get_sentiment(code: str = Query("", description="股票代码，为空则返回大盘情绪")):
    """获取情绪数据，提供 code 时返回个股情绪。

    Param:
        code: 股票代码（查询参数），为空将返回提示信息。
    Return:
        dict: 个股情绪指标或提示消息。
    """
    logger.info(f"获取情绪数据: code={code or '大盘'}")
    try:
        if code:
            return await get_stock_sentiment_service(code)
        return {"message": "请提供股票代码"}
    except Exception as e:
        logger.error(f"获取情绪数据失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取情绪数据失败: {e}")


@router.get("/retail-sentiment")
async def get_retail_sentiment(code: str = Query(..., description="股票代码")):
    """获取个股散户情绪指标。

    Param:
        code: 股票代码（查询参数），必填。
    Return:
        dict: 散户情绪相关指标与详情。
    """
    logger.info(f"获取散户情绪数据: code={code}")
    try:
        return await get_retail_sentiment_service(code)
    except Exception as e:
        logger.error(f"获取散户情绪数据失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取散户情绪数据失败: {e}")


@router.get("/news-categorized")
async def get_news_categorized(code: str = Query(..., description="股票代码")):
    """获取按类别分组的个股新闻流。

    Param:
        code: 股票代码（查询参数），必填。
    Return:
        dict: 按公告、新闻、研报等类别整理的新闻条目。
    """
    logger.info(f"获取分类新闻数据: code={code}")
    try:
        return await get_stock_news_categorized_service(code)
    except Exception as e:
        logger.error(f"获取分类新闻数据失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取分类新闻数据失败: {e}")


@router.get("/feed")
async def get_market_feed():
    """获取 24 小时市场新闻流。

    Return:
        list[dict] | dict: 综合多源的新闻列表，按时间倒序。
    """
    logger.info("获取24小时新闻流")
    try:
        return await get_market_feed_service()
    except Exception as e:
        logger.error(f"获取新闻流失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取新闻流失败: {e}")


@router.get("/kuaixun")
async def get_market_kuaixun():
    """获取 7×24 快讯流（多源合并去重，分钟级刷新）。

    Return:
        list[dict]: 快讯列表，source 统一为 "7×24 快讯"。
    """
    logger.info("获取7×24快讯流")
    try:
        return await get_market_kuaixun_service()
    except Exception as e:
        logger.error(f"获取快讯流失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取快讯流失败: {e}")


@router.get("/other-news")
async def get_market_other_news():
    """获取非快讯类新闻（30 分钟刷新）。

    Return:
        list[dict]: 新闻列表，按时间倒序。
    """
    logger.info("获取其他新闻")
    try:
        return await get_market_other_news_service()
    except Exception as e:
        logger.error(f"获取其他新闻失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取其他新闻失败: {e}")


@router.get("/industry-rankings")
async def get_industry_rankings():
    """获取行业板块涨跌幅排名。

    Return:
        list[dict]: 行业名称、涨跌幅及成交活跃度排序。
    """
    logger.info("获取行业板块涨跌幅排名")
    try:
        return await get_industry_rankings_service()
    except Exception as e:
        logger.error(f"获取行业板块涨跌幅排名失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取行业板块涨跌幅排名失败: {e}")


@router.get("/news-analysis")
async def get_news_analysis():
    """获取由 LLM 生成的市场资讯综合分析。

    Return:
        dict: AI 汇总的市场资讯解读与要点。
    """
    logger.info("获取AI资讯分析")
    try:
        return await analyze_market_news_service()
    except Exception as e:
        logger.error(f"获取AI资讯分析失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取AI资讯分析失败: {e}")
