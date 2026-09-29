import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

from app.agentic.events import AgentEvent, auditable_agent_event
from app.agentic.public import (
    AgentEvidence,
    AgentEvidenceInsufficientError,
    AgenticResearchResult,
    agent_evidence_id,
)
from app.agentic.tools.serialization import serialize_result
from app.configuration import get_effective_settings
from app.core.cache import analysis_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.errors import log_internal_error
from app.core.progress import ProgressEmitter
from app.domain.industry_chain import (
    IndustryChainResearchScope,
    render_industry_chain_scope,
    resolve_industry_chain_scope,
)
from app.infrastructure.llm.policy import LLMGenerationTimeoutError
from app.infrastructure.llm.prompting import PromptExecutionError, run_structured_prompt
from app.modules.industry_chain import research as industry_research
from app.modules.industry_chain.archive_service import (
    get_latest_industry_chain_archive,
    load_industry_chain_archive,
)
from app.modules.industry_chain.atlas.context import (
    atlas_expected_segments as _atlas_expected_segments,
)
from app.modules.industry_chain.atlas.context import (
    matching_atlas_chain as _matching_atlas_chain,
)
from app.modules.industry_chain.atlas.context import (
    render_atlas_prior as _render_atlas_prior,
)
from app.modules.industry_chain.atlas.miner import auto_mine_from_result
from app.modules.industry_chain.chain_reasoning import validate_chain_reasoning
from app.modules.industry_chain.charts import build_industry_charts, build_relationship_chart
from app.modules.industry_chain.diff import compute_industry_chain_changes
from app.modules.industry_chain.events import IndustryChainProgress
from app.modules.industry_chain.evidence import (
    build_evidence_catalog,
    compact_industry_evidence,
    compact_public_industry_data,
    validate_claim_support,
    validate_result_evidence_ids,
    validate_result_source_urls,
)
from app.modules.industry_chain.evidence_context import (
    PUBLIC_DATA_KEYS as _PUBLIC_DATA_KEYS,
)
from app.modules.industry_chain.evidence_context import (
    collection_item_count as _collection_item_count,
)
from app.modules.industry_chain.evidence_context import (
    evidence_inventory as _evidence_inventory,
)
from app.modules.industry_chain.evidence_context import (
    has_public_data as _has_public_data,
)
from app.modules.industry_chain.evidence_context import (
    independent_source_count as _independent_source_count,
)
from app.modules.industry_chain.evidence_context import (
    public_evidence_items as _public_evidence_items,
)
from app.modules.industry_chain.evidence_context import (
    public_evidence_reference as _public_evidence_reference,
)
from app.modules.industry_chain.evidence_context import (
    usable_agent_evidence_count as _usable_agent_evidence_count,
)
from app.modules.industry_chain.insights import build_opportunities, build_topic_resolution
from app.modules.industry_chain.models import (
    IndustryChainAnalysisMetadata,
    IndustryChainEvidenceStats,
    IndustryChainResult,
)
from app.modules.industry_chain.normalizer import (
    result_from_payload,
)
from app.modules.industry_chain.persistence.repository import save_industry_chain
from app.modules.industry_chain.prompts import INDUSTRY_CHAIN_PROMPT_SPEC
from app.modules.industry_chain.public_collector import collect_public_industry_data
from app.modules.industry_chain.quality_gate import (
    add_missing_evidence as _add_missing_evidence,
)
from app.modules.industry_chain.quality_gate import (
    add_warning as _add_warning,
)
from app.modules.industry_chain.quality_gate import (
    apply_quality_gate as _apply_quality_gate,
)
from app.modules.industry_chain.relationships import validate_relationships
from app.modules.industry_chain.report_renderer import render_industry_markdown
from app.modules.industry_chain.result_policy import (
    IndustryChainReportUnavailableError,
    recover_prompt_result,
)
from app.modules.industry_chain.result_policy import (
    industry_chain_cache_key as _industry_chain_cache_key,
)
from app.modules.industry_chain.result_policy import (
    result_cache_ttl as _result_cache_ttl,
)
from app.modules.industry_chain.templates import select_research_template
from app.modules.industry_chain.verification_repair import build_repair_targets, repair_report

logger = logging.getLogger(__name__)
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()

_research_industry_chain: Callable[..., Awaitable[AgenticResearchResult]] = industry_research.research_industry_chain
_collect_public_industry_data: Callable[..., Awaitable[dict[str, Any]]] = collect_public_industry_data
_result_from_payload: Callable[[str, dict[str, Any]], IndustryChainResult] = result_from_payload

_RESEARCH_STAGE = "research"
_DRAFT_STAGE = "draft"
_VERIFICATION_STAGE = "verification"
_FINALIZE_STAGE = "finalize"
_ARCHIVE_STAGE = "archive"
_MAX_PUBLIC_CONTEXT_LENGTH = 20_000
def _start_background_task(coro, *, name: str) -> None:
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


def _load_cached_result(cache_key: str, *, force: bool) -> IndustryChainResult | None:
    if force:
        return None
    cached = cache.get(cache_key)
    if cached is None:
        return None
    return cached if isinstance(cached, IndustryChainResult) else IndustryChainResult.model_validate(cached)


def _event(
    *,
    event_type: Literal["stage_started", "stage_completed", "stage_failed", "agent_event", "complete", "error"],
    stage: str,
    message: str,
    result: IndustryChainResult | None = None,
    agent_event=None,
) -> IndustryChainProgress:
    return IndustryChainProgress(
        type=event_type,
        stage=stage,
        message=message,
        result=result,
        agent_event=agent_event,
        archive_id=result.archive_id if result is not None else "",
        archive_status=result.archive_status if result is not None else "none",
        quality_status=result.quality_status if result is not None else "complete",
        warnings=list(result.warnings) if result is not None else [],
    )


async def run_industry_chain_analysis(
    name: str,
    user_id: int,
    progress_callback=None,
    *,
    scope: IndustryChainResearchScope | None = None,
    force: bool = False,
    before_persist: Callable[[], Awaitable[None]] | None = None,
) -> IndustryChainResult:
    """执行产业链数据采集、结构化生成和结果存档。"""
    total_started_at = time.perf_counter()
    progress = ProgressEmitter(progress_callback)
    resolved_scope = resolve_industry_chain_scope(scope)
    # Keep the resolved as-of/trading date in the whole-report cache key. Dimension
    # caches still provide cheap reuse, while a prior-day report never masks fresh market data.
    cache_key = _industry_chain_cache_key(user_id, name, resolved_scope)
    cached_result = _load_cached_result(cache_key, force=force or bool(resolved_scope.refresh_dimensions))
    if cached_result is not None:
        await progress.emit(_event(
            event_type="complete",
            stage="cached",
            message="使用缓存结果",
            result=cached_result,
        ))
        return cached_result

    settings = get_effective_settings()

    try:
        await progress.emit(_event(
            event_type="stage_started",
            stage=_RESEARCH_STAGE,
            message="正在并行采集公共数据并开展 Agent 调研与证据校验...",
        ))

        async def emit_agent_event(event: AgentEvent) -> None:
            public_event = auditable_agent_event(event)
            if public_event is None:
                return
            await progress.emit(_event(
                event_type="agent_event",
                stage=_RESEARCH_STAGE,
                message="",
                agent_event=public_event,
            ))

        atlas_chain = _matching_atlas_chain(name)
        atlas_prior = _render_atlas_prior(atlas_chain)
        expected_segments = _atlas_expected_segments(atlas_chain)
        research_started_at = time.perf_counter()
        outcomes = await asyncio.gather(
            _research_industry_chain(
                name,
                settings=settings,
                scope=resolved_scope,
                atlas_prior=atlas_prior,
                event_callback=emit_agent_event if progress_callback is not None else None,
            ),
            _collect_public_industry_data(name, resolved_scope),
            return_exceptions=True,
        )
        research_outcome = cast(AgenticResearchResult | Exception, outcomes[0])
        public_outcome = cast(dict[str, Any] | Exception, outcomes[1])

        warnings: list[str] = []
        public_data: dict[str, Any] = {}
        collection_metadata: dict[str, Any] = {}
        if isinstance(public_outcome, Exception):
            logger.warning("产业链公共数据采集失败: name=%s, error=%s", name, public_outcome)
            _add_warning(warnings, "公共结构化数据采集失败，本次报告仅使用 Agent 工具证据")
        elif isinstance(public_outcome, dict):
            raw_collection_metadata = public_outcome.get("_collection_metadata")
            if isinstance(raw_collection_metadata, dict):
                collection_metadata = raw_collection_metadata
            if _has_public_data(public_outcome):
                public_data = public_outcome
            else:
                _add_warning(warnings, "公共结构化数据未返回有效内容，本次报告仅使用 Agent 工具证据")
        else:
            _add_warning(warnings, "公共结构化数据未返回有效内容，本次报告仅使用 Agent 工具证据")

        fallback_research = False
        research_evidence: tuple[AgentEvidence, ...] = ()
        evidence_stats = None
        if isinstance(research_outcome, AgentEvidenceInsufficientError):
            fallback_research = True
            logger.warning("产业链 Agent 证据覆盖不足，结合可用信息降级生成: name=%s, error=%s", name, research_outcome)
            _add_warning(warnings, f"Agent 调研部分证据缺失（{research_outcome}），已使用现有数据综合生成")
            # 异常里带着本轮已采集的证据：fatal 门没过不等于一条证据都没拿到，
            # 直接丢掉就只能拿公共数据硬推，报告质量与可追溯性都会塌掉。
            research_evidence = tuple(research_outcome.evidence)
            summary = research_outcome.summary or ""
            if research_evidence:
                _, rendered_evidence, evidence_stats = compact_industry_evidence(
                    research_evidence,
                    focus_terms=(name, *select_research_template(name).metrics),
                )
                research_context = {
                    "agent_summary": (
                        f"产业链「{name}」调研部分完成。注意：{research_outcome}。"
                        f"{summary}以下分析基于已取得的证据综合评估。"
                    ),
                    "agent_evidence": rendered_evidence,
                }
            else:
                research_context = {
                    "agent_summary": f"产业链「{name}」调研完成。注意：{research_outcome}。以下分析基于现有可用公开信息综合评估。",
                    "agent_evidence": "本轮未取得可追溯证据，已使用可用数据推演。",
                }
        elif isinstance(research_outcome, Exception):
            raise research_outcome
        else:
            if research_outcome.stopped_early:
                fallback_research = True
                _add_warning(warnings, "Agent摘要未完整生成；已保留工具证据，停止额外调研与补证，仅合成降级报告。")
            research_evidence = research_outcome.evidence
            _, rendered_evidence, evidence_stats = compact_industry_evidence(
                research_evidence, focus_terms=(name, *select_research_template(name).metrics)
            )
            research_context = {
                "agent_summary": research_outcome.summary,
                "agent_evidence": rendered_evidence,
            }

        await progress.emit(_event(
            event_type="stage_completed",
            stage=_RESEARCH_STAGE,
            message="数据采集、Agent 调研与证据校验完成",
        ))
        research_duration_ms = round((time.perf_counter() - research_started_at) * 1000)

        compacted_public_data = compact_public_industry_data(public_data) if public_data else {}
        public_serialized = (
            serialize_result(compacted_public_data, _MAX_PUBLIC_CONTEXT_LENGTH)
            if public_data
            else "暂无可用公共结构化数据"
        )
        all_evidence = list(research_evidence)
        public_evidence = _public_evidence_items(name, public_data)
        public_evidence_id = _public_evidence_reference(public_evidence)
        all_evidence.extend(public_evidence)
        evidence_catalog = build_evidence_catalog(all_evidence)
        if evidence_stats is None:
            evidence_stats = IndustryChainEvidenceStats()
        if public_data:
            evidence_stats = evidence_stats.model_copy(update={
                "total_count": evidence_stats.total_count + len(public_evidence),
                "unique_count": evidence_stats.unique_count + len(public_evidence),
                "selected_count": evidence_stats.selected_count + len(public_evidence),
                "omitted_count": evidence_stats.omitted_count,
                "prompt_characters": evidence_stats.prompt_characters + len(public_serialized),
            })
        evidence_compaction_note = (
            f"共 {evidence_stats.total_count} 次工具/公共数据调用，去重后 {evidence_stats.unique_count} 条，"
            f"最终向合成模型提供 {evidence_stats.selected_count} 条，省略 {evidence_stats.omitted_count} 条。"
        )
        agent_evidence_gaps = (
            "、".join(research_outcome.evidence_gaps)
            if not isinstance(research_outcome, Exception) and research_outcome.evidence_gaps
            else "无"
        )

        prompt_context = {
            "name": name,
            "research_scope": render_industry_chain_scope(resolved_scope),
            "atlas_prior": atlas_prior,
            **research_context,
            "public_data": public_serialized,
            "public_evidence_id": public_evidence_id,
            "company_scope": resolved_scope.company_scope,
            "evidence_compaction_note": evidence_compaction_note,
            "agent_evidence_gaps": agent_evidence_gaps,
            "evidence_inventory": _evidence_inventory(
                public_data,
                agent_evidence_count=evidence_stats.selected_count - len(public_evidence),
            ),
        }
        synthesis_started_at = time.perf_counter()
        draft_started_at = synthesis_started_at
        await progress.emit(_event(
            event_type="stage_started",
            stage=_DRAFT_STAGE,
            message="AI 正在生成结构化产业链初稿...",
        ))
        result: IndustryChainResult
        structured_prompt_succeeded = False
        try:
            prompt_run = await run_structured_prompt(
                INDUSTRY_CHAIN_PROMPT_SPEC,
                prompt_context,
                settings=settings.model_copy(update={"llm_timeout_seconds": settings.analysis_llm_timeout_seconds}),
                timeout_seconds=settings.analysis_llm_timeout_seconds,
                max_tokens=settings.analysis_llm_max_completion_tokens,
            )
            result = _result_from_payload(name, prompt_run.value.model_dump())
            structured_prompt_succeeded = True
            result.prompt_trace = prompt_run.trace
            result.warnings.extend(warnings)
            if fallback_research:
                result.quality_status = "degraded"
        except PromptExecutionError as prompt_exc:
            recovered = recover_prompt_result(name, prompt_exc.raw_response, _result_from_payload)
            if recovered is None:
                raise IndustryChainReportUnavailableError(
                    "结构化报告生成失败，且未能恢复出包含摘要和产业链节点的可用报告"
                ) from prompt_exc
            result = recovered
            result.prompt_trace = prompt_exc.trace
            result.quality_status = "degraded"
            result.warnings.extend(warnings)
            _add_warning(result.warnings, "结构化报告未通过完整校验，已恢复可用字段；请结合证据目录谨慎使用")
            result.missing_evidence.append("结构化报告输出未通过完整校验，请重新分析")
            logger.warning("产业链 Prompt 校验失败，已恢复可用降级报告: name=%s", name)

        draft_duration_ms = round((time.perf_counter() - draft_started_at) * 1000)
        await progress.emit(_event(event_type="stage_completed", stage=_DRAFT_STAGE, message="结构化产业链初稿生成完成"))
        verification_started_at = time.perf_counter()
        await progress.emit(_event(event_type="stage_started", stage=_VERIFICATION_STAGE, message="正在校验引用、传导关系并按需定向补证..."))

        result.research_scope = resolved_scope.model_dump(mode="json", exclude_none=True, exclude={"refresh_dimensions"})
        if not isinstance(research_outcome, Exception):
            result.agent_trace = list(research_outcome.execution_trace)
        result.evidence_catalog = evidence_catalog
        result.evidence_stats = evidence_stats
        if not isinstance(research_outcome, Exception):
            for gap in research_outcome.evidence_gaps:
                _add_missing_evidence(result, f"Agent 调研仍缺少「{gap}」证据")
            if research_outcome.evidence_gaps:
                result.quality_status = "degraded"
        unknown_evidence_ids = validate_result_evidence_ids(result, evidence_catalog)
        if unknown_evidence_ids:
            result.quality_status = "degraded"
            _add_warning(result.warnings, "报告引用了不存在的工具证据 ID，已自动移除")
        mismatched_source_urls = validate_result_source_urls(result, evidence_catalog)
        if mismatched_source_urls:
            result.quality_status = "degraded"
            _add_warning(result.warnings, "部分来源链接不属于所引用的工具证据，已自动移除")

        validate_claim_support(result, all_evidence)
        validate_relationships(result)
        validate_chain_reasoning(result)
        if structured_prompt_succeeded and not (isinstance(research_outcome, AgenticResearchResult) and research_outcome.stopped_early) and build_repair_targets(result, all_evidence):
            await emit_agent_event(AgentEvent(
                type="status",
                content=f"正在对核心判断和重点公司进行有界补证（最多{getattr(settings, 'industry_chain_repair_tool_calls_total', 48)}次工具调用）...",
            ))
            original_trace = list(result.agent_trace)
            result, all_evidence, repair_trace = await repair_report(
                name, result, all_evidence, settings=settings, scope=resolved_scope,
                prompt_context=prompt_context,
                event_callback=emit_agent_event if progress_callback is not None else None,
            )
            result.agent_trace = original_trace + repair_trace
            result.research_scope = resolved_scope.model_dump(mode="json", exclude_none=True, exclude={"refresh_dimensions"})
            result.evidence_catalog = build_evidence_catalog(all_evidence)
            if result.verification_repair.status == "completed":
                evidence_stats = result.evidence_stats
            else:
                result.evidence_stats = evidence_stats.model_copy(update={
                    "total_count": len(all_evidence),
                    "unique_count": len({agent_evidence_id(item) for item in all_evidence}),
                    "omitted_count": max(0, len(all_evidence) - evidence_stats.selected_count),
                    "failed_count": sum(item.is_error for item in all_evidence),
                })
                evidence_stats = result.evidence_stats
            for warning in warnings:
                _add_warning(result.warnings, warning)
            if fallback_research:
                result.quality_status = "degraded"

        try:
            from app.financial_data.stock.profile.name_map import get_stock_name_map
            name_map = await get_stock_name_map()
            if name_map:
                from app.modules.industry_chain.normalizer import enrich_result_stock_codes
                result = enrich_result_stock_codes(result, name_map)
        except Exception as enrich_exc:
            logger.debug("股票代码自动富化跳过: %s", enrich_exc)

        verification_duration_ms = round((time.perf_counter() - verification_started_at) * 1000)
        await progress.emit(_event(event_type="stage_completed", stage=_VERIFICATION_STAGE, message="引用校验与定向补证完成"))
        finalization_started_at = time.perf_counter()
        await progress.emit(_event(event_type="stage_started", stage=_FINALIZE_STAGE, message="正在生成图表并执行最终质量检查..."))

        result.topic_resolution = build_topic_resolution(name, result, public_data)
        _apply_quality_gate(result, resolved_scope, expected_segments)
        validate_relationships(result)
        validate_chain_reasoning(result)
        result.charts = build_industry_charts(result)
        relationship_chart = build_relationship_chart(result)
        if relationship_chart is not None:
            result.charts.append(relationship_chart)
        result.opportunities = build_opportunities(result)
        if structured_prompt_succeeded:
            result.llm_review = render_industry_markdown(result)
        finalization_duration_ms = round((time.perf_counter() - finalization_started_at) * 1000)
        await progress.emit(_event(event_type="stage_completed", stage=_FINALIZE_STAGE, message="图表与最终质量检查完成"))
        synthesis_duration_ms = round((time.perf_counter() - synthesis_started_at) * 1000)

        def metadata_dimensions(key: str) -> list[str]:
            value = collection_metadata.get(key)
            if not isinstance(value, list):
                return []
            return sorted({str(item) for item in value if str(item).strip()})

        public_item_count = sum(
            _collection_item_count(public_data.get(key)) for key in _PUBLIC_DATA_KEYS
        )
        result.analysis_metadata = IndustryChainAnalysisMetadata(
            research_duration_ms=research_duration_ms,
            synthesis_duration_ms=synthesis_duration_ms,
            draft_duration_ms=draft_duration_ms,
            verification_duration_ms=verification_duration_ms,
            finalization_duration_ms=finalization_duration_ms,
            cache_hits=metadata_dimensions("cache_hits"),
            cache_misses=metadata_dimensions("cache_misses"),
            failed_dimensions=metadata_dimensions("failed_dimensions"),
            successful_dimensions=metadata_dimensions("successful_dimensions"),
            agent_evidence_count=_usable_agent_evidence_count(all_evidence),
            public_item_count=public_item_count,
            independent_source_count=_independent_source_count(result.evidence_catalog),
        )

        archive_started_at = time.perf_counter()
        await progress.emit(_event(event_type="stage_started", stage=_ARCHIVE_STAGE, message="正在保存报告并更新历史版本..."))
        try:
            previous_archive = await get_latest_industry_chain_archive(
                name,
                user_id,
                can_delete_legacy=False,
            )
            previous_result = None
            if previous_archive.archive_id:
                previous_result = await load_industry_chain_archive(
                    name,
                    previous_archive.archive_id,
                    user_id,
                )
            result.changes = compute_industry_chain_changes(
                previous_result,
                result,
                previous_archive_id=previous_archive.archive_id,
            )
        except Exception as diff_exc:
            logger.warning("产业链版本差异计算失败: name=%s, error=%s", name, diff_exc)

        if before_persist is not None:
            await before_persist()
        try:
            archive_id = await call_blocking(
                save_industry_chain,
                name,
                result,
                user_id,
                semaphore=misc_semaphore,
            )
            result.archive_id = archive_id
            result.archive_status = "saved"
        except Exception as save_exc:
            result.archive_id = ""
            result.archive_status = "failed"
            _add_warning(result.warnings, "报告已生成，但保存失败；当前结果无法推送，请重新分析")
            logger.warning("产业链存档失败: name=%s, error=%s", name, save_exc)

        await progress.emit(_event(
            event_type="stage_completed" if result.archive_status == "saved" else "stage_failed",
            stage=_ARCHIVE_STAGE,
            message="报告归档与历史更新完成" if result.archive_status == "saved" else "报告已生成，但存档失败",
        ))
        result.analysis_metadata.archive_duration_ms = round(
            (time.perf_counter() - archive_started_at) * 1000
        )
        result.analysis_metadata.total_duration_ms = round(
            (time.perf_counter() - total_started_at) * 1000
        )

        if result.archive_status == "saved":
            # A cancelled/lease-lost job must not update shared atlas or result cache.
            if before_persist is not None:
                await before_persist()
            if result.quality_status == "complete":
                _start_background_task(
                    auto_mine_from_result(result),
                    name=f"industry_atlas_auto_mining:{result.name}",
                )
            cache.set(
                cache_key,
                result,
                ttl=_result_cache_ttl(result),
            )

        message = "分析完成" if result.quality_status == "complete" else "分析完成，但报告存在质量提示"
        if result.archive_status == "failed":
            message = f"{message}；存档失败"
        await progress.emit(_event(
            event_type="complete",
            stage="done",
            message=message,
            result=result,
        ))
        return result
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
        await progress.emit(_event(
            event_type="error",
            stage="error",
            message=detail,
        ))
        raise
