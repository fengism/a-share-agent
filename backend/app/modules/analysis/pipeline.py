import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import cast
from uuid import uuid4

from app.agentic.events import AgentEvent, auditable_agent_event
from app.agentic.public import AgentEvidenceInsufficientError
from app.configuration import get_effective_settings
from app.core.cache import analysis_cache as cache
from app.core.errors import log_internal_error
from app.core.progress import ProgressCallback, ProgressEmitter, StageClock
from app.core.timezones import SHANGHAI_TIMEZONE
from app.infrastructure.llm.streaming import LLMGenerationTimeoutError
from app.modules.analysis import result_service, stages
from app.modules.analysis.events import ANALYSIS_STAGE_NAMES, AnalysisProgress, AnalysisStage
from app.modules.analysis.key_levels import apply_key_levels, resolve_key_levels
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence import repository as analysis_storage
from app.modules.analysis.provenance import build_provenance

logger = logging.getLogger(__name__)


def _analysis_date(now: datetime | None = None) -> str:
    return (now or datetime.now(SHANGHAI_TIMEZONE)).astimezone(SHANGHAI_TIMEZONE).strftime("%Y%m%d")


async def _emit_stage_started(
    progress: ProgressEmitter[AnalysisProgress],
    stage: int,
    *,
    detail: str = "",
) -> StageClock:
    await progress.emit(
        AnalysisProgress(
            type="stage_started",
            stage=AnalysisStage(
                stage=stage,
                name=ANALYSIS_STAGE_NAMES[stage],
                status="started",
                detail=detail,
            ),
        )
    )
    return StageClock.start()


async def _emit_stage_completed(
    progress: ProgressEmitter[AnalysisProgress],
    stage: int,
    clock: StageClock,
) -> None:
    await progress.emit(
        AnalysisProgress(
            type="stage_completed",
            stage=AnalysisStage(
                stage=stage,
                name=ANALYSIS_STAGE_NAMES[stage],
                status="completed",
                duration_ms=clock.elapsed_ms(),
            ),
        )
    )


async def run_analysis(
    code: str,
    user_id: int,
    progress_callback: ProgressCallback[AnalysisProgress] | None = None,
    *,
    force: bool = False,
    before_persist: Callable[[], Awaitable[None]] | None = None,
) -> AnalysisResult:
    """Run the full stock analysis pipeline (data fetch, indicators, LLM, persist)."""
    progress = ProgressEmitter(progress_callback)
    analysis_date = _analysis_date()
    cache_key = analysis_storage.analysis_cache_key(user_id, code, analysis_date)
    cached = None if force else cache.get(cache_key)
    if cached is not None:
        cached_result = AnalysisResult.model_validate(cached)
        if cached_result.research_framework is not None:
            await progress.emit(AnalysisProgress(type="cached", result=cached_result))
            return cast(AnalysisResult, cached_result)
        cache.delete(cache_key)
        logger.info("忽略旧版个股分析缓存并重新生成: code=%s", code)

    settings = get_effective_settings()
    active_stage = 1
    research_started_at = datetime.now(SHANGHAI_TIMEZONE)
    try:
        clock = await _emit_stage_started(
            progress,
            1,
            detail="Agent 正在自主选择工具、补齐证据并校验覆盖度...",
        )

        async def emit_agent_event(event: AgentEvent) -> None:
            public_event = auditable_agent_event(event)
            if public_event is not None:
                await progress.emit(AnalysisProgress(
                    type="agent_event",
                    agent_event=public_event,
                ))

        research, key_levels = await asyncio.gather(
            stages.research_stock(
                code,
                analysis_date,
                settings,
                event_callback=emit_agent_event if progress_callback is not None else None,
            ),
            resolve_key_levels(code),
        )
        research_completed_at = datetime.now(SHANGHAI_TIMEZONE)
        await _emit_stage_completed(progress, 1, clock)

        active_stage = 2
        clock = await _emit_stage_started(progress, 2)
        prompt_context = stages.build_prompt_context(code, analysis_date, research)
        logger.info("[Pipeline] prompt ready: code=%s", code)
        await _emit_stage_completed(progress, 2, clock)

        active_stage = 3
        clock = await _emit_stage_started(
            progress,
            3,
            detail="正在生成完整投研报告，支持流式接收；完成后将校验输出…",
        )
        await emit_agent_event(AgentEvent(
            type="status",
            content=(
                f"全维度证据采集完毕（共 {len(research.evidence)} 条事实证据），"
                "正在基于多空博弈框架合成深度投研报告…"
            ),
        ))

        async def _report_generation_heartbeat():
            started_at = asyncio.get_running_loop().time()
            step_tips = [
                "正在解析财务报表与估值情景…",
                "正在推演商业壁垒、护城河反证与管理层资本配置…",
                "正在从空头做空视角进行逆向压力测试与失败路径推演…",
                "正在执行结构化校验、证据缺口降级与买卖行动规划…",
            ]
            interval = 10
            count = 0
            while True:
                await asyncio.sleep(interval)
                elapsed = int(asyncio.get_running_loop().time() - started_at)
                tip = step_tips[count % len(step_tips)]
                count += 1
                await emit_agent_event(AgentEvent(
                    type="status",
                    content=(f"深度研报生成中（已等待 {elapsed} 秒，{tip}）"
                             f"（本次时限 {settings.analysis_llm_timeout_seconds:g} 秒）…"),
                ))

        thinking_task = asyncio.create_task(_report_generation_heartbeat())
        try:
            result = await stages.generate_analysis_result(code, prompt_context, settings)
        finally:
            thinking_task.cancel()
            await asyncio.gather(thinking_task, return_exceptions=True)

        await _emit_stage_completed(progress, 3, clock)
        active_stage = 4
        clock = await _emit_stage_started(progress, 4, detail="校验结构化结果，记录证据来源、报告期与缓存状态")
        result = apply_key_levels(result, key_levels)
        result = cast(
            AnalysisResult,
            result.model_copy(update={
                "agent_trace": list(research.execution_trace),
                "report_id": uuid4().hex, "analysis_date": analysis_date,
                "generated_at": datetime.now(SHANGHAI_TIMEZONE).isoformat(),
                "provenance": build_provenance(research, started_at=research_started_at, completed_at=research_completed_at, force=force),
            }),
        )
        result = AnalysisResult.model_validate(result.model_dump())
        await _emit_stage_completed(progress, 4, clock)
        active_stage = 5
        clock = await _emit_stage_started(progress, 5, detail="写入独立报告版本并更新当天最新报告，成功后才标记完成")
        if before_persist is not None:
            await before_persist()
        await result_service.persist_analysis_result(
            result,
            user_id=user_id,
            cache_key=cache_key,
            cache_ttl_seconds=settings.cache_ttl_analysis,
        )
        await _emit_stage_completed(progress, 5, clock)
        logger.info(
            "[Pipeline] 分析完成: %s, 评分=%s, 信号=%s",
            code,
            result.overall_rating,
            result.signal,
        )
        await progress.emit(AnalysisProgress(type="complete", result=result))
        return result
    except Exception as error:
        if progress_callback is not None:
            if isinstance(error, result_service.AnalysisArchiveError):
                detail = str(error)
            elif isinstance(error, LLMGenerationTimeoutError):
                detail = str(error)
                logger.warning("个股分析超时: code=%s, error=%s", code, detail)
            elif isinstance(error, AgentEvidenceInsufficientError):
                detail = str(error)
                logger.warning("个股 Agent 调研证据不足: code=%s, error=%s", code, detail)
            else:
                _, detail = log_internal_error(
                    logger,
                    "个股分析",
                    error,
                    "分析失败，请稍后重试",
                )
            await progress.emit(AnalysisProgress(type="stage_failed", stage=AnalysisStage(
                stage=active_stage, name=ANALYSIS_STAGE_NAMES[active_stage], status="failed", detail=detail,
            )))
            await progress.emit(AnalysisProgress(type="error", error=detail))
        raise
