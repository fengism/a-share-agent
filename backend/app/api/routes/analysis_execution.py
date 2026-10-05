"""AI 分析触发、结果读取与流式执行 HTTP 端点。"""

import logging

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.auth.dependencies import require_active_user
from app.api.errors import ConflictError, NotFoundError, ServiceUnavailableError, TooManyRequestsError
from app.api.streaming import SSE_RESPONSES
from app.configuration import get_settings
from app.domain.identity import AuthenticatedUser
from app.modules.analysis.public import (
    AnalysisResult,
    WorkflowCapacityError,
    create_analysis_event_generator,
    load_latest_analysis,
)
from app.modules.workflow.public import (
    WorkflowExecutionError,
    submit_analysis_workflow,
    wait_for_workflow_result,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{code}", response_model=AnalysisResult)
async def trigger_analysis(code: str, user: AuthenticatedUser = Depends(require_active_user)):
    """触发指定股票的同步 AI 分析。

    Param:
        code: 股票代码（路径参数），A 股 6 位数字或港股 1-5 位数字。
    Return:
        AnalysisResult: 完整的结构化分析结果，包含评级、信号与目标价等字段。
    """

    logger.info("触发AI分析: code=%s, user_id=%s", code, user["id"])
    try:
        submission = await submit_analysis_workflow(code, user["id"], force=False)
    except WorkflowCapacityError as error:
        raise TooManyRequestsError(
            "分析任务队列已满，请等待已有任务完成",
            code=f"workflow.{error.scope}_capacity_reached",
            retry_after_seconds=30,
        ) from error
    try:
        payload = await wait_for_workflow_result(
            submission.job.id,
            user["id"],
            timeout_seconds=get_settings().chat_total_timeout_seconds,
        )
    except WorkflowExecutionError as error:
        if error.cancelled:
            raise ConflictError("分析任务已取消", code="workflow.cancelled") from error
        raise ServiceUnavailableError(str(error), code="workflow.execution_failed") from error
    result = AnalysisResult.model_validate(payload)
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
        code: 股票代码（路径参数），A 股 6 位数字或港股 1-5 位数字。
    Return:
        dict | AnalysisResult: 缓存或落盘的最近一次分析结果；若不存在则抛出 404。
    """
    result = await load_latest_analysis(code, user["id"])
    if result is not None:
        return result

    logger.info("无缓存分析结果: code=%s", code)
    raise NotFoundError("暂无分析结果，请先触发分析", code="analysis.result_not_found")


@router.get("/{code}/stream", response_class=EventSourceResponse, responses=SSE_RESPONSES)
async def stream_analysis(code: str, user: AuthenticatedUser = Depends(require_active_user)):
    """SSE 端点，流式推送分析进度事件。

    Param:
        code: 股票代码（路径参数），A 股 6 位数字或港股 1-5 位数字；同一代码并发请求会附着到已有任务。
    Return:
        EventSourceResponse: SSE 流，依次发送 progress 事件并以哨兵结束。
    """
    try:
        event_generator = await create_analysis_event_generator(code, user["id"])
    except WorkflowCapacityError as error:
        raise TooManyRequestsError(
            "分析任务队列已满，请等待已有任务完成",
            code=f"workflow.{error.scope}_capacity_reached",
            retry_after_seconds=30,
        ) from error
    return EventSourceResponse(event_generator)
