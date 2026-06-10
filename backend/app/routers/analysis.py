import logging

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.analysis import AnalysisHistoryItem, AnalysisResult
from app.services.analysis.pipeline import run_analysis
from app.services.analysis.storage import (
    get_analysis_by_date as get_analysis_by_date_service,
    get_latest_analysis as get_latest_analysis_service,
    list_analyses,
    list_all_analyses,
)
from app.services.analysis.stream import (
    AnalysisAlreadyRunningError,
    create_analysis_event_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Static routes BEFORE parameterized /{code} routes ---


@router.get("/history/all", response_model=list[AnalysisHistoryItem])
async def get_all_analysis_history():
    """获取所有股票的历史 AI 分析记录列表。

    Return:
        list[AnalysisHistoryItem]: 全部历史分析条目集合。
    """
    return list_all_analyses()


# --- Parameterized routes ---


@router.post("/{code}", response_model=AnalysisResult)
async def trigger_analysis(code: str):
    """触发指定股票的同步 AI 分析。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        AnalysisResult: 完整的结构化分析结果，包含评级、信号与目标价等字段。
    """
    logger.info(f"触发AI分析: code={code}")
    try:
        result = await run_analysis(code)
        logger.info(f"AI分析完成: code={code}, rating={result.overall_rating}, signal={result.signal}, price={result.current_price}")
        return result
    except ValueError as e:
        logger.warning(f"AI分析参数错误: code={code}, error={e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"AI分析失败: code={code}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")


@router.get("/{code}/result")
async def get_analysis_result(code: str):
    """读取指定股票当天的最新分析结果，优先返回缓存。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict | AnalysisResult: 缓存或落盘的最近一次分析结果；若不存在则抛出 404。
    """
    result = get_latest_analysis_service(code)
    if result is not None:
        return result

    logger.info(f"无缓存分析结果: code={code}")
    raise HTTPException(status_code=404, detail="暂无分析结果，请先触发分析")


@router.get("/{code}/stream")
async def stream_analysis(code: str):
    """SSE 端点，流式推送分析进度事件。

    Param:
        code: 股票代码（路径参数），6 位数字；同一代码并发请求会返回 409。
    Return:
        EventSourceResponse: SSE 流，依次发送 progress 事件并以哨兵结束。
    """

    try:
        event_generator = await create_analysis_event_generator(code)
    except AnalysisAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return EventSourceResponse(event_generator)


@router.get("/{code}/history", response_model=list[AnalysisHistoryItem])
async def get_analysis_history(code: str):
    """读取指定股票的历史分析索引列表。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        list[AnalysisHistoryItem]: 按日期排序的历史分析摘要条目。
    """
    return list_analyses(code)


@router.get("/{code}/history/{date}", response_model=AnalysisResult)
async def get_analysis_by_date(code: str, date: str):
    """读取指定股票在指定日期的分析结果，命中缓存优先。

    Param:
        code: 股票代码（路径参数），6 位数字。
        date: 分析日期（路径参数），格式 YYYYMMDD。
    Return:
        AnalysisResult: 该日的完整分析结果；若不存在则返回 404。
    """
    result = get_analysis_by_date_service(code, date)
    if result is None:
        raise HTTPException(status_code=404, detail=f"未找到 {code} 在 {date} 的分析记录")
    return result
