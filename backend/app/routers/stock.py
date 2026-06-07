import logging

from fastapi import APIRouter, HTTPException, Query

from app.models.stock import FinancialMetrics, IntradayData, KlineData, StockBasicInfo, StockSearchItem, ValuationDetail
from app.services import technical
from app.services.analysis.news import get_stock_news as get_stock_news_service
from app.services.stock.basic_info import get_basic_info as get_basic_info_service
from app.services.stock.financials import get_financial as get_financial_service, get_financial_metrics as get_financial_metrics_service
from app.services.stock.intraday import get_intraday as get_intraday_service
from app.services.stock.kline import get_kline as get_stock_kline_service
from app.services.screener.percentiles import _compute_percentile
from app.services.stock.search import search_stocks as search_stock_items
from app.services.stock.valuation import get_valuation as get_valuation_service, get_valuation_detail as get_valuation_detail_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search", response_model=list[StockSearchItem])
async def search_stocks(q: str = Query(..., min_length=1, description="股票名称或代码")):
    """按名称或代码模糊搜索股票。

    Param:
        q: 查询关键字（查询参数），可为代码片段或股票名称，至少 1 个字符。
    Return:
        list[StockSearchItem]: 匹配到的股票候选条目。
    """
    logger.info(f"搜索股票: q={q}")
    try:
        result = await search_stock_items(q)
        logger.info(f"搜索结果: q={q}, 匹配{len(result)}条")
        return result
    except Exception as e:
        logger.error(f"搜索失败: q={q}, error={e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router.get("/{code}/info", response_model=StockBasicInfo)
async def get_stock_info(code: str):
    """获取个股基本资料。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        StockBasicInfo: 公司名称、所属行业、上市信息等基础数据。
    """
    logger.info(f"获取股票信息: code={code}")
    try:
        return await get_basic_info_service(code)
    except ValueError as e:
        logger.warning(f"股票信息参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取股票信息失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取信息失败: {e}")


@router.get("/{code}/kline", response_model=KlineData)
async def get_kline(
    code: str,
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    start_date: str = Query(""),
    end_date: str = Query(""),
    adjust: str = Query("qfq", pattern="^(qfq|hfq|)$"),
):
    """获取个股 K 线数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
        period: K 线周期（查询参数），daily / weekly / monthly。
        start_date: 起始日期（查询参数），格式 YYYYMMDD，可留空。
        end_date: 结束日期（查询参数），格式 YYYYMMDD，可留空。
        adjust: 复权类型（查询参数），qfq、hfq 或空字符串表示不复权。
    Return:
        KlineData: 按时间排序的 K 线条目集合。
    """
    logger.info(f"获取K线: code={code}, period={period}, adjust={adjust}")
    try:
        return await get_stock_kline_service(code, period, start_date, end_date, adjust)
    except ValueError as e:
        logger.warning(f"K线参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取K线失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取K线失败: {e}")


@router.get("/{code}/financial")
async def get_financial(code: str, type: str = Query("balance", pattern="^(balance|profit|cashflow)$")):
    """获取个股财务报表数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
        type: 报表类型（查询参数），balance / profit / cashflow。
    Return:
        dict: 对应报表的多期数据。
    """
    logger.info(f"获取财务数据: code={code}, type={type}")
    try:
        return await get_financial_service(code, type)
    except ValueError as e:
        logger.warning(f"财务数据参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取财务数据失败: code={code}, type={type}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取财务数据失败: {e}")


@router.get("/{code}/intraday", response_model=IntradayData)
async def get_intraday(code: str):
    """获取个股分时数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        IntradayData: 当日分时价、量、均价等序列。
    """
    logger.info(f"获取分时数据: code={code}")
    try:
        return await get_intraday_service(code)
    except ValueError as e:
        logger.warning(f"分时数据参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取分时数据失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取分时数据失败: {e}")


@router.get("/{code}/financial-metrics", response_model=FinancialMetrics)
async def get_financial_metrics(code: str):
    """获取个股关键财务指标汇总。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        FinancialMetrics: 营收、利润、ROE 等核心财务指标。
    """
    logger.info(f"获取财务指标: code={code}")
    try:
        return await get_financial_metrics_service(code)
    except ValueError as e:
        logger.warning(f"财务指标参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取财务指标失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取财务指标失败: {e}")


@router.get("/{code}/valuation")
async def get_valuation(code: str):
    """获取个股估值数据。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: PE、PB、市值等估值指标。
    """
    logger.info(f"获取估值数据: code={code}")
    try:
        return await get_valuation_service(code)
    except ValueError as e:
        logger.warning(f"估值参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取估值数据失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取估值数据失败: {e}")


@router.get("/{code}/valuation-detail", response_model=ValuationDetail)
async def get_valuation_detail(code: str):
    """获取个股估值详情，包括历史分位与对比指标。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        ValuationDetail: 当前估值、历史分位以及相关明细。
    """
    logger.info(f"获取估值详情: code={code}")
    try:
        return await get_valuation_detail_service(code, _compute_percentile)
    except ValueError as e:
        logger.warning(f"估值详情参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取估值详情失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取估值详情失败: {e}")


@router.get("/{code}/news")
async def get_news(code: str):
    """获取个股最新新闻流。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        list[dict] | dict: 按时间排序的新闻条目集合。
    """
    logger.info(f"获取新闻: code={code}")
    try:
        return await get_stock_news_service(code)
    except Exception as e:
        logger.error(f"获取新闻失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"获取新闻失败: {e}")


@router.get("/{code}/indicators")
async def get_indicators(code: str):
    """基于日 K 线计算个股常用技术指标。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict: 包含 RSI、MACD、KDJ 等技术指标的字典。
    """
    logger.info(f"计算技术指标: code={code}")
    try:
        kline = await get_stock_kline_service(code)
        indicators = technical.calculate_all(kline.items)
        logger.info(f"技术指标计算完成: code={code}, 数据点={len(kline.items)}, RSI={indicators['rsi']}")
        return indicators
    except ValueError as e:
        logger.warning(f"技术指标参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"计算技术指标失败: code={code}, error={e}")
        raise HTTPException(status_code=500, detail=f"计算技术指标失败: {e}")
