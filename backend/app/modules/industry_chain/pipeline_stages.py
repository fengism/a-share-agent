"""产业链分析管道各阶段处理器定义。

将原本长达数百行的单体执行函数拆分为高内聚、可独立测试的阶段处理器：
1. ResearchStage：并行公共数据采集与 Agent 证据调研；
2. DraftStage：初稿 Prompt 生成与异常恢复；
3. VerificationStage：证据校验、定向补证与股票画像富化；
4. FinalizeStage：质量门禁、可视化图表生成与元数据装配；
5. ArchiveStage：版本差异比对、持久化存档与自动挖掘缓存。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

from app.agentic.events import AgentEvent
from app.agentic.public import (
    AgentEvidence,
    AgentEvidenceInsufficientError,
    AgenticResearchResult,
    agent_evidence_id,
)
from app.agentic.tools.serialization import serialize_result
from app.core.cache import analysis_cache as cache
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.domain.industry_chain import render_industry_chain_scope
from app.infrastructure.llm.prompting import PromptExecutionError, run_structured_prompt
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
from app.modules.industry_chain.enrichment import enrich_industry_chain_stock_data
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
from app.modules.industry_chain.persistence.repository import save_industry_chain
from app.modules.industry_chain.pipeline_context import PipelineContext
from app.modules.industry_chain.prompts import INDUSTRY_CHAIN_PROMPT_SPEC
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
    result_cache_ttl as _result_cache_ttl,
)
from app.modules.industry_chain.templates import select_research_template
from app.modules.industry_chain.verification_repair import build_repair_targets, repair_report

logger = logging.getLogger(__name__)

_RESEARCH_STAGE = "research"
_DRAFT_STAGE = "draft"
_VERIFICATION_STAGE = "verification"
_FINALIZE_STAGE = "finalize"
_ARCHIVE_STAGE = "archive"
_MAX_PUBLIC_CONTEXT_LENGTH = 20_000


async def execute_research_stage(
    ctx: PipelineContext,
    research_fn: Callable[..., Awaitable[AgenticResearchResult]],
    collect_public_fn: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """阶段一：并行公共数据采集与 Agent 调研证据收集。"""
    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_started",
            stage=_RESEARCH_STAGE,
            message="正在并行采集公共数据并开展 Agent 调研与证据校验...",
        )
    )
    await ctx.check_cancellation()

    ctx.atlas_chain = _matching_atlas_chain(ctx.name, user_id=ctx.user_id)
    ctx.atlas_prior = _render_atlas_prior(ctx.atlas_chain)
    ctx.expected_segments = _atlas_expected_segments(ctx.atlas_chain)
    ctx.research_started_at = time.perf_counter()

    outcomes = await asyncio.gather(
        research_fn(
            ctx.name,
            settings=ctx.settings,
            scope=ctx.resolved_scope,
            atlas_prior=ctx.atlas_prior,
            event_callback=ctx.emit_agent_event if ctx.progress is not None else None,
        ),
        collect_public_fn(ctx.name, ctx.resolved_scope),
        return_exceptions=True,
    )
    await ctx.check_cancellation()
    research_outcome = cast(AgenticResearchResult | Exception, outcomes[0])
    public_outcome = cast(dict[str, Any] | Exception, outcomes[1])
    ctx.research_outcome = research_outcome

    # 1. 公共数据校验与提取
    if isinstance(public_outcome, Exception):
        logger.warning("产业链公共数据采集失败: name=%s, error=%s", ctx.name, public_outcome)
        _add_warning(ctx.warnings, "公共结构化数据采集失败，本次报告仅使用 Agent 工具证据")
    elif isinstance(public_outcome, dict):
        raw_metadata = public_outcome.get("_collection_metadata")
        if isinstance(raw_metadata, dict):
            ctx.collection_metadata = raw_metadata
        if _has_public_data(public_outcome):
            ctx.public_data = public_outcome
        else:
            _add_warning(ctx.warnings, "公共结构化数据未返回有效内容，本次报告仅使用 Agent 工具证据")
    else:
        _add_warning(ctx.warnings, "公共结构化数据未返回有效内容，本次报告仅使用 Agent 工具证据")

    # 2. Agent 调研证据校验与压缩
    research_evidence: tuple[AgentEvidence, ...] = ()
    evidence_stats: IndustryChainEvidenceStats | None = None
    if isinstance(research_outcome, AgentEvidenceInsufficientError):
        ctx.fallback_research = True
        logger.warning("产业链 Agent 证据覆盖不足，结合可用信息降级生成: name=%s, error=%s", ctx.name, research_outcome)
        _add_warning(ctx.warnings, f"Agent 调研部分证据缺失（{research_outcome}），已使用现有数据综合生成")
        research_evidence = tuple(research_outcome.evidence)
        summary = research_outcome.summary or ""
        if research_evidence:
            _, rendered_evidence, evidence_stats = compact_industry_evidence(
                research_evidence,
                focus_terms=(ctx.name, *select_research_template(ctx.name).metrics),
            )
            research_context = {
                "agent_summary": (
                    f"产业链「{ctx.name}」调研部分完成。注意：{research_outcome}。"
                    f"{summary}以下分析基于已取得的证据综合评估。"
                ),
                "agent_evidence": rendered_evidence,
            }
        else:
            research_context = {
                "agent_summary": f"产业链「{ctx.name}」调研完成。注意：{research_outcome}。以下分析基于现有可用公开信息综合评估。",
                "agent_evidence": "本轮未取得可追溯证据，已使用可用数据推演。",
            }
    elif isinstance(research_outcome, Exception):
        raise research_outcome
    else:
        if research_outcome.stopped_early:
            ctx.fallback_research = True
            _add_warning(ctx.warnings, "Agent摘要未完整生成；已保留工具证据，停止额外调研与补证，仅合成降级报告。")
        research_evidence = research_outcome.evidence
        _, rendered_evidence, evidence_stats = compact_industry_evidence(
            research_evidence, focus_terms=(ctx.name, *select_research_template(ctx.name).metrics)
        )
        research_context = {
            "agent_summary": research_outcome.summary,
            "agent_evidence": rendered_evidence,
        }

    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_completed",
            stage=_RESEARCH_STAGE,
            message="数据采集、Agent 调研与证据校验完成",
        )
    )
    ctx.research_duration_ms = round((time.perf_counter() - ctx.research_started_at) * 1000)

    # 3. 证据目录与提示词上下文装配
    compacted_public = compact_public_industry_data(ctx.public_data) if ctx.public_data else {}
    public_serialized = (
        serialize_result(compacted_public, _MAX_PUBLIC_CONTEXT_LENGTH) if ctx.public_data else "暂无可用公共结构化数据"
    )
    all_evidence = list(research_evidence)
    public_evidence = _public_evidence_items(ctx.name, ctx.public_data)
    public_evidence_id = _public_evidence_reference(public_evidence)
    all_evidence.extend(public_evidence)
    ctx.all_evidence = all_evidence
    ctx.evidence_catalog = build_evidence_catalog(all_evidence)

    if evidence_stats is None:
        evidence_stats = IndustryChainEvidenceStats()
    if ctx.public_data:
        evidence_stats = evidence_stats.model_copy(
            update={
                "total_count": evidence_stats.total_count + len(public_evidence),
                "unique_count": evidence_stats.unique_count + len(public_evidence),
                "selected_count": evidence_stats.selected_count + len(public_evidence),
                "omitted_count": evidence_stats.omitted_count,
                "prompt_characters": evidence_stats.prompt_characters + len(public_serialized),
            }
        )
    ctx.evidence_stats = evidence_stats

    evidence_compaction_note = (
        f"共 {evidence_stats.total_count} 次工具/公共数据调用，去重后 {evidence_stats.unique_count} 条，"
        f"最终向合成模型提供 {evidence_stats.selected_count} 条，省略 {evidence_stats.omitted_count} 条。"
    )
    agent_evidence_gaps = (
        "、".join(research_outcome.evidence_gaps)
        if not isinstance(research_outcome, Exception) and research_outcome.evidence_gaps
        else "无"
    )

    ctx.prompt_context = {
        "name": ctx.name,
        "research_scope": render_industry_chain_scope(ctx.resolved_scope),
        "atlas_prior": ctx.atlas_prior,
        **research_context,
        "public_data": public_serialized,
        "public_evidence_id": public_evidence_id,
        "company_scope": ctx.resolved_scope.company_scope,
        "evidence_compaction_note": evidence_compaction_note,
        "agent_evidence_gaps": agent_evidence_gaps,
        "evidence_inventory": _evidence_inventory(
            ctx.public_data,
            agent_evidence_count=evidence_stats.selected_count - len(public_evidence),
        ),
    }


async def execute_draft_stage(
    ctx: PipelineContext,
    result_from_payload_fn: Callable[[str, dict[str, Any]], IndustryChainResult],
) -> None:
    """阶段二：调用大模型生成结构化初稿并支持错误自愈。"""
    ctx.synthesis_started_at = time.perf_counter()
    ctx.draft_started_at = ctx.synthesis_started_at

    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_started",
            stage=_DRAFT_STAGE,
            message="AI 正在生成结构化产业链初稿...",
        )
    )
    await ctx.check_cancellation()

    try:
        prompt_run = await run_structured_prompt(
            INDUSTRY_CHAIN_PROMPT_SPEC,
            ctx.prompt_context,
            settings=ctx.settings.model_copy(update={"llm_timeout_seconds": ctx.settings.analysis_llm_timeout_seconds}),
            timeout_seconds=ctx.settings.analysis_llm_timeout_seconds,
            max_tokens=ctx.settings.analysis_llm_max_completion_tokens,
        )
        ctx.result = result_from_payload_fn(ctx.name, prompt_run.value.model_dump())
        ctx.structured_prompt_succeeded = True
        ctx.result.prompt_trace = prompt_run.trace
        ctx.result.warnings.extend(ctx.warnings)
        if ctx.fallback_research:
            ctx.result.quality_status = "degraded"
    except PromptExecutionError as prompt_exc:
        recovered = recover_prompt_result(ctx.name, prompt_exc.raw_response, result_from_payload_fn)
        if recovered is None:
            raise IndustryChainReportUnavailableError(
                "结构化报告生成失败，且未能恢复出包含摘要和产业链节点的可用报告"
            ) from prompt_exc
        ctx.result = recovered
        ctx.result.prompt_trace = prompt_exc.trace
        ctx.result.quality_status = "degraded"
        ctx.result.warnings.extend(ctx.warnings)
        _add_warning(ctx.result.warnings, "结构化报告未通过完整校验，已恢复可用字段；请结合证据目录谨慎使用")
        ctx.result.missing_evidence.append("结构化报告输出未通过完整校验，请重新分析")
        logger.warning("产业链 Prompt 校验失败，已恢复可用降级报告: name=%s", ctx.name)

    ctx.save_checkpoint("draft")
    ctx.draft_duration_ms = round((time.perf_counter() - ctx.draft_started_at) * 1000)
    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_completed",
            stage=_DRAFT_STAGE,
            message="结构化产业链初稿生成完成",
            result=ctx.result,
        )
    )


async def execute_verification_stage(ctx: PipelineContext) -> None:
    """阶段三：证据引用审计、传导关系校验、定向补证与重点标的行情富化。"""
    ctx.verification_started_at = time.perf_counter()
    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_started",
            stage=_VERIFICATION_STAGE,
            message="正在校验引用、传导关系并按需定向补证...",
        )
    )
    await ctx.check_cancellation()

    result = ctx.result
    assert result is not None, "初稿报告未初始化"

    result.research_scope = ctx.resolved_scope.model_dump(
        mode="json", exclude_none=True, exclude={"refresh_dimensions"}
    )
    if not isinstance(ctx.research_outcome, Exception):
        result.agent_trace = list(ctx.research_outcome.execution_trace)
    result.evidence_catalog = ctx.evidence_catalog
    result.evidence_stats = ctx.evidence_stats

    if not isinstance(ctx.research_outcome, Exception):
        for gap in ctx.research_outcome.evidence_gaps:
            _add_missing_evidence(result, f"Agent 调研仍缺少「{gap}」证据")
        if ctx.research_outcome.evidence_gaps:
            result.quality_status = "degraded"

    unknown_evidence_ids = validate_result_evidence_ids(result, ctx.evidence_catalog)
    if unknown_evidence_ids:
        result.quality_status = "degraded"
        _add_warning(result.warnings, "报告引用了不存在的工具证据 ID，已自动移除")

    mismatched_urls = validate_result_source_urls(result, ctx.evidence_catalog)
    if mismatched_urls:
        result.quality_status = "degraded"
        _add_warning(result.warnings, "部分来源链接不属于所引用的工具证据，已自动移除")

    validate_claim_support(result, ctx.all_evidence)
    validate_relationships(result)
    validate_chain_reasoning(result)

    # 触发定向补证
    if (
        ctx.structured_prompt_succeeded
        and not (isinstance(ctx.research_outcome, AgenticResearchResult) and ctx.research_outcome.stopped_early)
        and build_repair_targets(result, ctx.all_evidence)
    ):
        await ctx.check_cancellation()
        await ctx.emit_agent_event(
            AgentEvent(
                type="status",
                content=f"正在对核心判断和重点公司进行有界补证（最多{getattr(ctx.settings, 'industry_chain_repair_tool_calls_total', 48)}次工具调用）...",
            )
        )
        original_trace = list(result.agent_trace)
        result, ctx.all_evidence, repair_trace = await repair_report(
            ctx.name,
            result,
            ctx.all_evidence,
            settings=ctx.settings,
            scope=ctx.resolved_scope,
            prompt_context=ctx.prompt_context,
            event_callback=ctx.emit_agent_event if ctx.progress is not None else None,
        )
        result.agent_trace = original_trace + repair_trace
        result.research_scope = ctx.resolved_scope.model_dump(
            mode="json", exclude_none=True, exclude={"refresh_dimensions"}
        )
        result.evidence_catalog = build_evidence_catalog(ctx.all_evidence)
        if result.verification_repair.status == "completed":
            ctx.evidence_stats = result.evidence_stats
        else:
            result.evidence_stats = ctx.evidence_stats.model_copy(
                update={
                    "total_count": len(ctx.all_evidence),
                    "unique_count": len({agent_evidence_id(item) for item in ctx.all_evidence}),
                    "omitted_count": max(0, len(ctx.all_evidence) - ctx.evidence_stats.selected_count),
                    "failed_count": sum(item.is_error for item in ctx.all_evidence),
                }
            )
            ctx.evidence_stats = result.evidence_stats
        for warning in ctx.warnings:
            _add_warning(result.warnings, warning)
        if ctx.fallback_research:
            result.quality_status = "degraded"

    # 富化股票代码与最新市值/估值快照
    ctx.result = await enrich_industry_chain_stock_data(result)
    ctx.save_checkpoint("verification")

    ctx.verification_duration_ms = round((time.perf_counter() - ctx.verification_started_at) * 1000)
    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_completed",
            stage=_VERIFICATION_STAGE,
            message="引用校验与定向补证完成",
            result=ctx.result,
        )
    )


async def execute_finalize_stage(ctx: PipelineContext) -> None:
    """阶段四：主题裁决、图表构建、质量门禁与分析元数据组装。"""
    ctx.finalization_started_at = time.perf_counter()
    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_started",
            stage=_FINALIZE_STAGE,
            message="正在生成图表并执行最终质量检查...",
        )
    )
    await ctx.check_cancellation()

    result = ctx.result
    assert result is not None, "报告未初始化"

    result.topic_resolution = build_topic_resolution(ctx.name, result, ctx.public_data)
    _apply_quality_gate(result, ctx.resolved_scope, ctx.expected_segments)
    validate_relationships(result)
    validate_chain_reasoning(result)

    result.charts = build_industry_charts(result)
    rel_chart = build_relationship_chart(result)
    if rel_chart is not None:
        result.charts.append(rel_chart)

    result.opportunities = build_opportunities(result)
    if ctx.structured_prompt_succeeded:
        result.llm_review = render_industry_markdown(result)

    ctx.finalization_duration_ms = round((time.perf_counter() - ctx.finalization_started_at) * 1000)
    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_completed",
            stage=_FINALIZE_STAGE,
            message="图表与最终质量检查完成",
            result=ctx.result,
        )
    )

    ctx.synthesis_duration_ms = round((time.perf_counter() - ctx.synthesis_started_at) * 1000)

    def metadata_dimensions(key: str) -> list[str]:
        value = ctx.collection_metadata.get(key)
        if not isinstance(value, list):
            return []
        return sorted({str(item) for item in value if str(item).strip()})

    public_item_count = sum(_collection_item_count(ctx.public_data.get(k)) for k in _PUBLIC_DATA_KEYS)
    result.analysis_metadata = IndustryChainAnalysisMetadata(
        research_duration_ms=ctx.research_duration_ms,
        synthesis_duration_ms=ctx.synthesis_duration_ms,
        draft_duration_ms=ctx.draft_duration_ms,
        verification_duration_ms=ctx.verification_duration_ms,
        finalization_duration_ms=ctx.finalization_duration_ms,
        cache_hits=metadata_dimensions("cache_hits"),
        cache_misses=metadata_dimensions("cache_misses"),
        failed_dimensions=metadata_dimensions("failed_dimensions"),
        successful_dimensions=metadata_dimensions("successful_dimensions"),
        agent_evidence_count=_usable_agent_evidence_count(ctx.all_evidence),
        public_item_count=public_item_count,
        independent_source_count=_independent_source_count(result.evidence_catalog),
    )


async def execute_archive_stage(
    ctx: PipelineContext,
    start_background_task_fn: Callable[[Any, str], None],
    cache_key: str,
) -> None:
    """阶段五：版本差异比对、持久化存档、自动知识沉淀与缓存。"""
    result = ctx.result
    assert result is not None, "报告未初始化"

    ctx.archive_started_at = time.perf_counter()
    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_started",
            stage=_ARCHIVE_STAGE,
            message="正在保存报告并更新历史版本...",
        )
    )
    await ctx.check_cancellation()

    try:
        prev_archive = await get_latest_industry_chain_archive(
            ctx.name,
            ctx.user_id,
            can_delete_legacy=False,
        )
        prev_result = None
        if prev_archive.archive_id:
            prev_result = await load_industry_chain_archive(
                ctx.name,
                prev_archive.archive_id,
                ctx.user_id,
            )
        result.changes = compute_industry_chain_changes(
            prev_result,
            result,
            previous_archive_id=prev_archive.archive_id,
        )
    except Exception as diff_exc:
        logger.warning("产业链版本差异计算失败: name=%s, error=%s", ctx.name, diff_exc)

    await ctx.check_cancellation()
    if ctx.before_persist is not None:
        await ctx.before_persist()

    try:
        archive_id = await call_blocking(
            save_industry_chain,
            ctx.name,
            result,
            ctx.user_id,
            semaphore=misc_semaphore,
        )
        result.archive_id = archive_id
        result.archive_status = "saved"
    except Exception as save_exc:
        result.archive_id = ""
        result.archive_status = "failed"
        _add_warning(result.warnings, "报告已生成，但保存失败；当前结果无法推送，请重新分析")
        logger.warning("产业链存档失败: name=%s, error=%s", ctx.name, save_exc)

    await ctx.progress.emit(
        ctx.make_event(
            event_type="stage_completed" if result.archive_status == "saved" else "stage_failed",
            stage=_ARCHIVE_STAGE,
            message="报告归档与历史更新完成" if result.archive_status == "saved" else "报告已生成，但存档失败",
        )
    )

    ctx.archive_duration_ms = round((time.perf_counter() - ctx.archive_started_at) * 1000)
    result.analysis_metadata.archive_duration_ms = ctx.archive_duration_ms
    result.analysis_metadata.total_duration_ms = round((time.perf_counter() - ctx.total_started_at) * 1000)

    if result.archive_status == "saved":
        if ctx.before_persist is not None:
            await ctx.before_persist()
        if result.quality_status == "complete":
            start_background_task_fn(
                auto_mine_from_result(result, user_id=ctx.user_id),
                f"industry_atlas_auto_mining:{result.name}:{ctx.user_id}",
            )
        cache.set(
            cache_key,
            result,
            ttl=_result_cache_ttl(result),
        )

    msg = "分析完成" if result.quality_status == "complete" else "分析完成，但报告存在质量提示"
    if result.archive_status == "failed":
        msg = f"{msg}；存档失败"

    await ctx.progress.emit(
        ctx.make_event(
            event_type="complete",
            stage="done",
            message=msg,
        )
    )
