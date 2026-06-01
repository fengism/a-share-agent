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
    logger.info(f"获取大盘成交量: start={start_date}, end={end_date}")
    try:
        return await get_market_volume_service(start_date,end_date)
    except Exception as e:
        logger.error(f"获取大盘成交量失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取成交量失败: {e}")


@router.get("/hsgt-flow")
async def get_hsgt_flow():
    logger.info("获取沪深股通分钟流向")
    try:
        return await get_hsgt_flow_service()
    except Exception as e:
        logger.error(f"获取沪深股通分钟流向失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取沪深股通分钟流向失败: {e}")


@router.get("/hot-stocks")
async def get_hot_stocks():
    logger.info("获取热门股排名")
    try:
        return await get_hot_stocks_service()
    except Exception as e:
        logger.error(f"获取热门股失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取热门股失败: {e}")


@router.get("/hot-rank/ths")
async def get_ths_hot_rank():
    logger.info("获取同花顺热股榜单")
    try:
        return await get_hot_stocks_service()
    except Exception as e:
        logger.error(f"获取同花顺热股榜单失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取同花顺热股榜单失败: {e}")


@router.get("/hot-rank/ths/concept")
async def get_ths_hot_concept():
    logger.info("获取同花顺热门概念")
    try:
        return await get_ths_hot_concept_service()
    except Exception as e:
        logger.error(f"获取同花顺热门概念失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取同花顺热门概念失败: {e}")


@router.get("/hot-rank/ths/industry")
async def get_ths_hot_industry():
    logger.info("获取同花顺热门行业")
    try:
        return await get_ths_hot_industry_service()
    except Exception as e:
        logger.error(f"获取同花顺热门行业失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取同花顺热门行业失败: {e}")


@router.get("/dragon-tiger")
async def get_dragon_tiger_list(report_date: str = Query("", description="报告日期 YYYY-MM-DD，默认当天")):
    logger.info(f"获取龙虎榜: date={report_date or '今天'}")
    try:
        return await get_dragon_tiger_list_service(report_date or None)
    except Exception as e:
        logger.error(f"获取龙虎榜失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取龙虎榜失败: {e}")


@router.get("/dragon-tiger/{code}")
async def get_dragon_tiger_detail(code: str, report_date: str = Query(..., description="报告日期 YYYY-MM-DD")):
    logger.info(f"获取龙虎榜明细: code={code}, date={report_date}")
    try:
        return await get_dragon_tiger_detail_service(code, report_date)
    except Exception as e:
        logger.error(f"获取龙虎榜明细失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取龙虎榜明细失败: {e}")


@router.get("/sentiment")
async def get_sentiment(code: str = Query("", description="股票代码，为空则返回大盘情绪")):
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
    logger.info(f"获取散户情绪数据: code={code}")
    try:
        return await get_retail_sentiment_service(code)
    except Exception as e:
        logger.error(f"获取散户情绪数据失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取散户情绪数据失败: {e}")


@router.get("/news-categorized")
async def get_news_categorized(code: str = Query(..., description="股票代码")):
    logger.info(f"获取分类新闻数据: code={code}")
    try:
        return await get_stock_news_categorized_service(code)
    except Exception as e:
        logger.error(f"获取分类新闻数据失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取分类新闻数据失败: {e}")


@router.get("/feed")
async def get_market_feed():
    logger.info("获取24小时新闻流")
    try:
        return await get_market_feed_service()
    except Exception as e:
        logger.error(f"获取新闻流失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取新闻流失败: {e}")


@router.get("/industry-rankings")
async def get_industry_rankings():
    logger.info("获取行业板块涨跌幅排名")
    try:
        return await get_industry_rankings_service()
    except Exception as e:
        logger.error(f"获取行业板块涨跌幅排名失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取行业板块涨跌幅排名失败: {e}")


@router.get("/news-analysis")
async def get_news_analysis():
    logger.info("获取AI资讯分析")
    try:
        return await analyze_market_news_service()
    except Exception as e:
        logger.error(f"获取AI资讯分析失败: error={e}")
        raise HTTPException(status_code=500, detail=f"获取AI资讯分析失败: {e}")
