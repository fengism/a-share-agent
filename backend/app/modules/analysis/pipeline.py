import logging
from datetime import datetime

from app.agentic.public import AgentEvidenceInsufficientError
from app.configuration import get_effective_settings
from app.core.cache import cache
from app.core.errors import log_internal_error
from app.core.progress import ProgressCallback, ProgressEmitter, StageClock
from app.modules.analysis import result_service, stages
from app.modules.analysis.events import ANALYSIS_STAGE_NAMES, AnalysisProgress, AnalysisStage
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence import repository as analysis_storage

logger = logging.getLogger(__name__)


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
) -> AnalysisResult:
    """Run the full stock analysis pipeline (data fetch, indicators, LLM, persist)."""
    progress = ProgressEmitter(progress_callback)
    analysis_date = datetime.now().strftime("%Y%m%d")
    cache_key = analysis_storage.analysis_cache_key(user_id, code, analysis_date)
    cached = cache.get(cache_key)
    if cached is not None:
        await progress.emit(AnalysisProgress(type="cached", result=cached))
        return cached

    settings = get_effective_settings()
    try:
        clock = await _emit_stage_started(
            progress,
            1,
            detail="Agent 正在自主选择工具、补齐证据并校验覆盖度...",
        )
        research = await stages.research_stock(code, analysis_date, settings)
        await _emit_stage_completed(progress, 1, clock)

        clock = await _emit_stage_started(progress, 2)
        prompt_context = stages.build_prompt_context(code, analysis_date, research)
        logger.info("[Pipeline] prompt ready: code=%s", code)
        await _emit_stage_completed(progress, 2, clock)

        clock = await _emit_stage_started(
            progress,
            3,
            detail="正在调用AI模型，可能需要10-25秒...",
        )
        result = await stages.generate_analysis_result(code, prompt_context, settings)
        await _emit_stage_completed(progress, 3, clock)

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
