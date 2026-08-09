"""AI 分析触发、结果读取与流式执行端点。"""

import logging

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.errors import ConflictError, NotFoundError
from app.api.streaming import SSE_RESPONSES
from app.configuration import get_effective_settings
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence.repository import get_latest_analysis as get_latest_analysis_service
from app.modules.analysis.pipeline import run_analysis
from app.modules.analysis.stream import AnalysisAlreadyRunningError, create_analysis_event_generator
from app.modules.auth.public import AuthenticatedUser, require_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{code}", response_model=AnalysisResult)
async def trigger_analysis(code: str, user: AuthenticatedUser = Depends(require_active_user)):
    """触发指定股票的同步 AI 分析。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        AnalysisResult: 完整的结构化分析结果，包含评级、信号与目标价等字段。
    """

    logger.info("触发AI分析: code=%s, user_id=%s", code, user["id"])
    result = await run_analysis(code, user["id"])
    logger.info(
        "AI分析完成: code=%s, rating=%s, signal=%s, price=%s",
        code,
        result.overall_rating,
        result.signal,
        result.current_price,
    )
    return result


@router.get("/{code}/result", response_model=AnalysisResult)
async def get_analysis_result(code: str, user: AuthenticatedUser = Depends(require_active_user)):
    """读取指定股票当天的最新分析结果，优先返回缓存。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        dict | AnalysisResult: 缓存或落盘的最近一次分析结果；若不存在则抛出 404。
    """
    result = await call_blocking(
        get_latest_analysis_service,
        code,
        user["id"],
        cache_ttl=get_effective_settings().cache_ttl_analysis,
        semaphore=misc_semaphore,
    )
    if result is not None:
        return result

    logger.info("无缓存分析结果: code=%s", code)
    raise NotFoundError("暂无分析结果，请先触发分析", code="analysis.result_not_found")


@router.get("/{code}/stream", response_class=EventSourceResponse, responses=SSE_RESPONSES)
async def stream_analysis(code: str, user: AuthenticatedUser = Depends(require_active_user)):
    """SSE 端点，流式推送分析进度事件。

    Param:
        code: 股票代码（路径参数），6 位数字；同一代码并发请求会返回 409。
    Return:
        EventSourceResponse: SSE 流，依次发送 progress 事件并以哨兵结束。
    """
    try:
        event_generator = await create_analysis_event_generator(code, user["id"])
    except AnalysisAlreadyRunningError as exc:
        raise ConflictError(str(exc), code="analysis.already_running") from exc

    return EventSourceResponse(event_generator)
