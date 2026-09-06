import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

from app.agentic.events import AgentEvent, auditable_agent_event
from app.agentic.public import AgentEvidenceInsufficientError
from app.configuration import get_effective_settings
from app.core.cache import analysis_cache as cache
from app.core.errors import log_internal_error
from app.core.progress import ProgressCallback, ProgressEmitter, StageClock
from app.modules.analysis import result_service, stages
from app.modules.analysis.events import ANALYSIS_STAGE_NAMES, AnalysisProgress, AnalysisStage
from app.modules.analysis.key_levels import apply_key_levels, resolve_key_levels
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence import repository as analysis_storage

logger = logging.getLogger(__name__)
_MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _analysis_date(now: datetime | None = None) -> str:
    return (now or datetime.now(_MARKET_TIMEZONE)).astimezone(_MARKET_TIMEZONE).strftime("%Y%m%d")


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
        await _emit_stage_completed(progress, 1, clock)

        clock = await _emit_stage_started(progress, 2)
        prompt_context = stages.build_prompt_context(code, analysis_date, research)
        logger.info("[Pipeline] prompt ready: code=%s", code)
        await _emit_stage_completed(progress, 2, clock)

        clock = await _emit_stage_started(
            progress,
            3,
            detail="AI 正在长思维链深度推理中（8大投研章节）...",
        )

        reasoning_milestones = [
            (0.0, "🧠 AI 开始深度推理：评估资料完备度与事实证据链…"),
            (3.0, "🔍 AI 正在解构商业模式、经济引擎与分部盈利质量…"),
            (6.5, "🏰 AI 正在校验护城河壁垒与潜在破坏因素…"),
            (10.0, "👔 AI 正在审查管理层历史业绩、资本配置与股东利益一致性…"),
            (13.5, "🌐 AI 正在审视行业格局、周期位置与产业链价值链分配…"),
            (17.0, "🐻 AI 正在进行最强逆向推演（Inversion Bear Case）与风险矩阵评估…"),
            (20.5, "⚖️ AI 正在构建三情景估值模型（Bull / Base / Bear）与公允价值区间…"),
            (24.0, "🎯 AI 正在生成行动建议触发器、核心跟踪指标与数据缺口汇总…"),
        ]

        async def _stream_thinking_milestones():
            for delay, milestone in reasoning_milestones:
                if delay > 0:
                    await asyncio.sleep(3.5)
                await emit_agent_event(AgentEvent(type="status", content=milestone))

        thinking_task = asyncio.create_task(_stream_thinking_milestones())
        try:
            result = await stages.generate_analysis_result(code, prompt_context, settings)
        finally:
            thinking_task.cancel()
            await asyncio.gather(thinking_task, return_exceptions=True)

        result = apply_key_levels(result, key_levels)
        result = cast(
            AnalysisResult,
            result.model_copy(update={"agent_trace": list(research.execution_trace)}),
        )
        await emit_agent_event(AgentEvent(type="status", content="✨ 8大投研章节已全部生成完毕，正在组装研报…"))
        await _emit_stage_completed(progress, 3, clock)

        if before_persist is not None:
            await before_persist()
        await result_service.persist_analysis_result(
            result,
            user_id=user_id,
            cache_key=cache_key,
            cache_ttl_seconds=settings.cache_ttl_analysis,
        )
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
            if isinstance(error, AgentEvidenceInsufficientError):
                detail = str(error)
                logger.warning("个股 Agent 调研证据不足: code=%s, error=%s", code, detail)
            else:
                _, detail = log_internal_error(
                    logger,
                    "个股分析",
                    error,
                    "分析失败，请稍后重试",
                )
            await progress.emit(AnalysisProgress(type="error", error=detail))
        raise
