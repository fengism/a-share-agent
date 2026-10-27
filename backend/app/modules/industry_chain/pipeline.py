"""产业链深度投研分析执行管道。

通过多阶段处理器协同编排，完成数据采集、Agent 调研、结构化初稿、引用校验与补证、
质量门禁以及版本归档全链路。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from app.agentic.public import (
    AgentEvidenceInsufficientError,
    AgenticResearchResult,
)
from app.configuration import get_effective_settings
from app.core.cache import analysis_cache as cache
from app.core.errors import log_internal_error
from app.core.progress import ProgressEmitter
from app.domain.industry_chain import (
    IndustryChainResearchScope,
    resolve_industry_chain_scope,
)
from app.infrastructure.llm.policy import LLMGenerationTimeoutError
from app.modules.industry_chain import research as industry_research
from app.modules.industry_chain.events import IndustryChainProgress
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.normalizer import result_from_payload
from app.modules.industry_chain.pipeline_context import PipelineContext
from app.modules.industry_chain.pipeline_stages import (
    execute_archive_stage,
    execute_draft_stage,
    execute_finalize_stage,
    execute_research_stage,
    execute_verification_stage,
)
from app.modules.industry_chain.public_collector import collect_public_industry_data
from app.modules.industry_chain.result_policy import (
    industry_chain_cache_key as _industry_chain_cache_key,
)

logger = logging.getLogger(__name__)
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()

_research_industry_chain: Callable[..., Awaitable[AgenticResearchResult]] = industry_research.research_industry_chain
_collect_public_industry_data: Callable[..., Awaitable[dict[str, Any]]] = collect_public_industry_data
_result_from_payload: Callable[[str, dict[str, Any]], IndustryChainResult] = result_from_payload


def _start_background_task(coro: Any, *, name: str) -> None:
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


def _load_cached_result(cache_key: str, *, force: bool) -> IndustryChainResult | None:
    if force:
        return None
    cached = cache.get(cache_key)
    if cached is None:
        return None
    result = cached if isinstance(cached, IndustryChainResult) else IndustryChainResult.model_validate(cached)
    try:
        from app.modules.industry_chain.enrichment import enrich_stock_market_snapshots

        result = enrich_stock_market_snapshots(result, refresh_existing=True)
    except Exception as enrich_exc:
        logger.debug("缓存结果刷新最新行情快照失败: %s", enrich_exc)
    return result


def _event(
    *,
    event_type: Literal["stage_started", "stage_completed", "stage_failed", "agent_event", "complete", "error"],
    stage: str,
    message: str,
    result: IndustryChainResult | None = None,
    agent_event=None,
) -> IndustryChainProgress:
    res = result
    if res is not None and event_type in ("stage_started", "stage_completed", "stage_failed"):
        if res.agent_trace or res.evidence_catalog:
            res = res.model_copy(update={"agent_trace": [], "evidence_catalog": []})
    return IndustryChainProgress(
        type=event_type,
        stage=stage,
        message=message,
        result=res,
        agent_event=agent_event,
        archive_id=res.archive_id if res is not None else "",
        archive_status=res.archive_status if res is not None else "none",
        quality_status=res.quality_status if res is not None else "complete",
        warnings=list(res.warnings) if res is not None else [],
    )


async def run_industry_chain_analysis(
    name: str,
    user_id: int,
    progress_callback=None,
    *,
    scope: IndustryChainResearchScope | None = None,
    force: bool = False,
    before_persist: Callable[[], Awaitable[None]] | None = None,
    resume_from_checkpoint: bool = False,
) -> IndustryChainResult:
    """执行产业链数据采集、结构化生成和结果存档（基于阶段化管道架构）。"""
    total_started_at = time.perf_counter()
    progress = ProgressEmitter(progress_callback)
    resolved_scope = resolve_industry_chain_scope(scope)
    cache_key = _industry_chain_cache_key(user_id, name, resolved_scope)
    cached_result = _load_cached_result(cache_key, force=force or bool(resolved_scope.refresh_dimensions))
    if cached_result is not None:
        await progress.emit(
            _event(
                event_type="complete",
                stage="cached",
                message="使用缓存结果",
                result=cached_result,
            )
        )
        return cached_result

    settings = get_effective_settings()
    ctx = PipelineContext(
        name=name,
        user_id=user_id,
        resolved_scope=resolved_scope,
        settings=settings,
        progress=progress,
        before_persist=before_persist,
        total_started_at=total_started_at,
    )

    try:
        # 断点续跑支持：优先检查并恢复可用阶段成果
        if not force and resume_from_checkpoint:
            if ctx.load_checkpoint("verification"):
                logger.info("产业链分析从 verification 检查点恢复: name=%s", name)
                await progress.emit(
                    _event(
                        event_type="stage_completed",
                        stage="checkpoint_resumed",
                        message="已从核验检查点增量恢复，正在执行终审与图表生成...",
                        result=ctx.result,
                    )
                )
                await execute_finalize_stage(ctx)
                await execute_archive_stage(
                    ctx,
                    lambda coro, task_name: _start_background_task(coro, name=task_name),
                    cache_key,
                )
                assert ctx.result is not None
                return ctx.result
            if ctx.load_checkpoint("draft"):
                logger.info("产业链分析从 draft 检查点恢复: name=%s", name)
                await progress.emit(
                    _event(
                        event_type="stage_completed",
                        stage="checkpoint_resumed",
                        message="已从初稿检查点恢复，正在执行引用校验与定向补证...",
                        result=ctx.result,
                    )
                )
                await execute_verification_stage(ctx)
                await execute_finalize_stage(ctx)
                await execute_archive_stage(
                    ctx,
                    lambda coro, task_name: _start_background_task(coro, name=task_name),
                    cache_key,
                )
                assert ctx.result is not None
                return ctx.result

        # 1. 调研阶段：并行公共数据采集与 Agent 调研
        await execute_research_stage(ctx, _research_industry_chain, _collect_public_industry_data)

        # 2. 初稿阶段：Prompt 合成与错误恢复
        await execute_draft_stage(ctx, _result_from_payload)

        # 3. 校验阶段：引用审计、定向补证与行情快照富化
        await execute_verification_stage(ctx)

        # 4. 终审阶段：质量门禁、可视化图表生成与元数据组装
        await execute_finalize_stage(ctx)

        # 5. 归档阶段：版本差异比对、持久化存档与自动挖掘沉淀
        await execute_archive_stage(
            ctx,
            lambda coro, task_name: _start_background_task(coro, name=task_name),
            cache_key,
        )

        assert ctx.result is not None, "管道执行完成但未生成报告结果"
        return ctx.result
    except asyncio.CancelledError:
        logger.info("产业链分析任务已被显式取消: name=%s", name)
        await progress.emit(
            _event(
                event_type="error",
                stage="error",
                message="产业链分析任务已取消",
            )
        )
        raise
    except Exception as exc:
        if isinstance(exc, LLMGenerationTimeoutError):
            detail = str(exc)
            logger.warning("产业链模型超时: name=%s", name)
        elif isinstance(exc, AgentEvidenceInsufficientError):
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
        await progress.emit(
            _event(
                event_type="error",
                stage="error",
                message=detail,
            )
        )
        raise
