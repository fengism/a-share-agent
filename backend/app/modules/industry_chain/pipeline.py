import logging

from app.agentic.public import AgentEvidenceInsufficientError
from app.configuration import get_effective_settings
from app.core.cache import cache
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.errors import log_internal_error
from app.core.progress import ProgressEmitter
from app.infrastructure.llm.prompting import PromptExecutionError, run_structured_prompt
from app.modules.industry_chain import research as industry_research
from app.modules.industry_chain.events import IndustryChainProgress
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.normalizer import (
    extract_llm_report,
    result_from_payload,
    unescape_json_string,
)
from app.modules.industry_chain.persistence.repository import save_industry_chain
from app.modules.industry_chain.prompts import INDUSTRY_CHAIN_PROMPT_SPEC

logger = logging.getLogger(__name__)

_research_industry_chain = industry_research.research_industry_chain
_result_from_payload = result_from_payload

_STAGES = [
    "Agent 调研与证据校验",
    "AI 生成分析报告",
]


async def run_industry_chain_analysis(
    name: str,
    user_id: int,
    progress_callback=None,
) -> IndustryChainResult:
    """执行产业链数据采集、结构化生成和结果存档。"""
    progress = ProgressEmitter(progress_callback)
    cache_key = INDUSTRY_CHAIN_PROMPT_SPEC.cache_key("user", user_id, name)
    cached = cache.get(cache_key)
    if cached is not None:
        await progress.emit(IndustryChainProgress(
            type="complete", stage="cached", message="使用缓存结果", result=cached.model_dump(),
        ))
        return cached

    settings = get_effective_settings()

    try:
        await progress.emit(IndustryChainProgress(
            type="stage_started", stage=_STAGES[0], message="Agent 正在开展多轮调研并校验必需证据...",
        ))

        async def emit_agent_event(event):
            await progress.emit(IndustryChainProgress(
                type="agent_event",
                stage=_STAGES[0],
                agent_event=event,
            ))

        research = await _research_industry_chain(
            name,
            settings=settings,
            event_callback=emit_agent_event if progress_callback is not None else None,
        )
        await progress.emit(IndustryChainProgress(
            type="stage_completed", stage=_STAGES[0], message="Agent 调研与证据校验完成",
        ))

        prompt_context = {"name": name, **research.render_prompt_context()}
        await progress.emit(IndustryChainProgress(
            type="stage_started", stage=_STAGES[1], message="AI 正在生成分析报告...",
        ))
        try:
            prompt_run = await run_structured_prompt(
                INDUSTRY_CHAIN_PROMPT_SPEC,
                prompt_context,
            )
            result = _result_from_payload(name, prompt_run.value.model_dump())
            result.prompt_trace = prompt_run.trace
        except PromptExecutionError as prompt_exc:
            text = prompt_exc.raw_response.strip()
            result = IndustryChainResult(name=name, schema_version=2)
            result.prompt_trace = prompt_exc.trace
            extracted = extract_llm_report(text)
            result.llm_review = unescape_json_string(extracted) if extracted else (text or "（AI 分析报告生成失败，请重试）")
            if extracted:
                logger.info("产业链 Prompt 校验失败，通过手动提取恢复 llm_report, name=%s", name)
            else:
                logger.warning("产业链 Prompt 校验失败，使用原始文本作为 llm_review, name=%s", name)

        try:
            await call_blocking(
                save_industry_chain,
                name,
                result,
                user_id,
                semaphore=misc_semaphore,
            )
        except Exception as save_exc:
            logger.warning("产业链存档失败: name=%s, error=%s", name, save_exc)

        await progress.emit(IndustryChainProgress(
            type="complete", stage="done", message="分析完成", result=result.model_dump(),
        ))
        return result
    except Exception as exc:
        if isinstance(exc, AgentEvidenceInsufficientError):
            detail = str(exc)
            logger.warning("产业链 Agent 调研证据不足: name=%s, error=%s", name, detail)
        elif progress_callback is not None:
            _, detail = log_internal_error(
                logger,
                "产业链分析",
                exc,
                "产业链分析失败，请稍后重试",
            )
        else:
            detail = "产业链分析失败，请稍后重试"
        await progress.emit(IndustryChainProgress(
            type="error", stage="error", message=detail,
        ))
        raise
