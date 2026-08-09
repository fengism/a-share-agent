import logging
from datetime import datetime

from app.agentic.public import AgentEvidenceInsufficientError
from app.configuration import get_effective_settings
from app.core.cache import cache
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.errors import log_internal_error
from app.core.progress import ProgressCallback, ProgressEmitter, StageClock
from app.infrastructure.llm.prompting import run_structured_prompt
from app.infrastructure.llm.sync_client import create_llm_client
from app.modules.analysis import research as analysis_research
from app.modules.analysis.events import AnalysisProgress, AnalysisStage
from app.modules.analysis.models import AnalysisResult
from app.modules.analysis.persistence import repository as analysis_storage
from app.modules.analysis.prompts import ANALYSIS_PROMPT_SPEC

logger = logging.getLogger(__name__)

_research_stock = analysis_research.research_stock


STAGE_NAMES = {
    1: "Agent 调研与证据校验",
    2: "构造结构化请求",
    3: "AI 综合分析",
}


async def run_analysis(
    code: str,
    user_id: int,
    progress_callback: ProgressCallback[AnalysisProgress] | None = None,
) -> AnalysisResult:
    """Run the full stock analysis pipeline (data fetch, indicators, LLM, persist).

    Param:
        code: 6-digit stock code to analyze
        progress_callback: optional async callback receiving AnalysisProgress events
    Return:
        the final validated AnalysisResult for the stock
    """
    progress = ProgressEmitter(progress_callback)
    # 检查缓存
    today = datetime.now().strftime("%Y%m%d")
    cache_key = analysis_storage.analysis_cache_key(user_id, code, today)
    cached = cache.get(cache_key)
    if cached is not None:
        await progress.emit(AnalysisProgress(type="cached", result=cached))
        return cached

    settings = get_effective_settings()

    try:
        stage_clock = StageClock.start()
        await progress.emit(AnalysisProgress(
            type="stage_started",
            stage=AnalysisStage(stage=1, name=STAGE_NAMES[1], status="started",
                                detail="Agent 正在自主选择工具、补齐证据并校验覆盖度..."),
        ))
        research = await _research_stock(code, today, settings=settings)

        await progress.emit(AnalysisProgress(
            type="stage_completed",
            stage=AnalysisStage(stage=1, name=STAGE_NAMES[1], status="completed",
                                duration_ms=stage_clock.elapsed_ms()),
        ))

        stage_clock = StageClock.start()
        await progress.emit(AnalysisProgress(
            type="stage_started",
            stage=AnalysisStage(stage=2, name=STAGE_NAMES[2], status="started"),
        ))
        prompt_context = {
            "stock_code": code,
            "analysis_date": today,
            **research.render_prompt_context(),
        }
        llm_client = create_llm_client(settings)

        logger.info("[Pipeline] prompt ready: code=%s", code)

        await progress.emit(AnalysisProgress(
            type="stage_completed",
            stage=AnalysisStage(stage=2, name=STAGE_NAMES[2], status="completed",
                                duration_ms=stage_clock.elapsed_ms()),
        ))

        stage_clock = StageClock.start()
        await progress.emit(AnalysisProgress(
            type="stage_started",
            stage=AnalysisStage(stage=3, name=STAGE_NAMES[3], status="started",
                                detail="正在调用AI模型，可能需要10-25秒..."),
        ))
        prompt_run = await run_structured_prompt(
            ANALYSIS_PROMPT_SPEC,
            prompt_context,
            settings=settings,
            client=llm_client,
            temperature=settings.llm_temperature,
        )
        result = AnalysisResult.model_validate({
            **prompt_run.value.model_dump(),
            "prompt_trace": prompt_run.trace,
        })
        await progress.emit(AnalysisProgress(
            type="stage_completed",
            stage=AnalysisStage(stage=3, name=STAGE_NAMES[3], status="completed",
                                duration_ms=stage_clock.elapsed_ms()),
        ))

        if result.stock_code != code:
            result = result.model_copy(update={"stock_code": code})

        # 缓存结果
        cache.set(cache_key, result, ttl=settings.cache_ttl_analysis)

        # 持久化到文件
        try:
            await call_blocking(
                analysis_storage.save_analysis,
                result,
                user_id,
                semaphore=misc_semaphore,
            )
        except Exception as save_err:
            logger.warning(f"分析结果持久化失败: {save_err}")

        logger.info(f"[Pipeline] 分析完成: {code}, 评分={result.overall_rating}, 信号={result.signal}")

        await progress.emit(AnalysisProgress(type="complete", result=result))
        return result

    except Exception as exc:
        if progress_callback is not None:
            if isinstance(exc, AgentEvidenceInsufficientError):
                detail = str(exc)
                logger.warning("个股 Agent 调研证据不足: code=%s, error=%s", code, detail)
            else:
                _, detail = log_internal_error(
                    logger,
                    "个股分析",
                    exc,
                    "分析失败，请稍后重试",
                )
            await progress.emit(AnalysisProgress(type="error", error=detail))
        raise
