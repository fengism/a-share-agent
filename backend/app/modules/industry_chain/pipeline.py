import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

from app.agentic.events import AgentEvent
from app.agentic.public import (
    AgentEvidence,
    AgentEvidenceInsufficientError,
    AgenticResearchResult,
    agent_evidence_id,
)
from app.agentic.tools.serialization import serialize_result
from app.configuration import get_effective_settings
from app.core.cache import cache
from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.core.errors import log_internal_error
from app.core.progress import ProgressEmitter
from app.domain.industry_chain import (
    IndustryChainResearchScope,
    render_industry_chain_scope,
    resolve_industry_chain_scope,
)
from app.infrastructure.llm.prompting import PromptExecutionError, run_structured_prompt
from app.modules.industry_chain import research as industry_research
from app.modules.industry_chain.atlas.miner import auto_mine_from_result
from app.modules.industry_chain.events import IndustryChainProgress
from app.modules.industry_chain.evidence import (
    build_evidence_catalog,
    compact_industry_evidence,
    compact_public_industry_data,
    validate_result_evidence_ids,
    validate_result_source_urls,
)
from app.modules.industry_chain.models import IndustryChainEvidenceStats, IndustryChainResult
from app.modules.industry_chain.normalizer import (
    result_from_payload,
)
from app.modules.industry_chain.persistence.repository import save_industry_chain
from app.modules.industry_chain.prompts import INDUSTRY_CHAIN_PROMPT_SPEC
from app.modules.industry_chain.public_collector import collect_public_industry_data
from app.modules.industry_chain.report_renderer import render_industry_markdown

logger = logging.getLogger(__name__)

_research_industry_chain: Callable[..., Awaitable[AgenticResearchResult]] = industry_research.research_industry_chain
_collect_public_industry_data: Callable[[str], Awaitable[dict[str, Any]]] = collect_public_industry_data
_result_from_payload: Callable[[str, dict[str, Any]], IndustryChainResult] = result_from_payload

_RESEARCH_STAGE = "research"
_SYNTHESIS_STAGE = "synthesis"
_MAX_PUBLIC_CONTEXT_LENGTH = 20_000


def _has_public_data(value: Any) -> bool:
    if value is None or isinstance(value, Exception):
        return False
    if isinstance(value, dict):
        if value.get("error"):
            return False
        return any(_has_public_data(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_public_data(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _add_warning(warnings: list[str], warning: str) -> None:
    if warning and warning not in warnings:
        warnings.append(warning)


def _apply_quality_gate(result: IndustryChainResult) -> None:
    missing: list[str] = []
    if not result.summary.strip():
        missing.append("核心摘要")
    if not (result.upstream or result.midstream or result.downstream):
        missing.append("产业链节点")
    if not result.sources:
        missing.append("可追溯来源")
    if missing:
        result.quality_status = "degraded"
        _add_warning(result.warnings, f"报告结构不完整，缺少：{'、'.join(missing)}")
    missing_core_coverage = [
        label
        for field, label in (("market", "市场"), ("chain", "产业链"), ("companies", "公司"))
        if getattr(result.coverage, field) == "missing"
    ]
    if missing_core_coverage:
        result.quality_status = "degraded"
        _add_warning(result.warnings, f"核心研究维度证据缺失：{'、'.join(missing_core_coverage)}")
    if result.conflicts:
        _add_warning(result.warnings, f"存在 {len(result.conflicts)} 组数据口径冲突，请结合证据目录核对")
    if result.evidence_catalog and result.summary.strip() and not result.summary_evidence_ids:
        result.quality_status = "degraded"
        _add_warning(result.warnings, "核心摘要尚未关联到具体工具证据 ID")

    traceable_items = [
        *result.market_metrics,
        *result.technology_routes,
        *result.upstream,
        *result.midstream,
        *result.downstream,
        *result.trends,
        *result.capital_moves,
        *result.key_events,
        *result.key_stocks,
        *(company for group in result.competition for company in group.companies),
    ]
    sourced_items = [item for item in traceable_items if str(getattr(item, "source", "")).strip()]
    linked_items = [item for item in sourced_items if str(getattr(item, "source_url", "")).strip()]
    if len(sourced_items) >= 2 and len(linked_items) * 2 < len(sourced_items):
        result.quality_status = "degraded"
        _add_warning(result.warnings, "多数结构化结论缺少可点击的原始来源链接")
    evidence_linked_items = [
        item for item in sourced_items if bool(getattr(item, "evidence_ids", []))
    ]
    if result.evidence_catalog and len(sourced_items) >= 2 and len(evidence_linked_items) * 2 < len(sourced_items):
        result.quality_status = "degraded"
        _add_warning(result.warnings, "多数结构化结论尚未关联到具体工具证据 ID")


def _event(
    *,
    event_type: Literal["stage_started", "stage_completed", "agent_event", "complete", "error"],
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
) -> IndustryChainResult:
    """执行产业链数据采集、结构化生成和结果存档。"""
    progress = ProgressEmitter(progress_callback)
    resolved_scope = resolve_industry_chain_scope(scope)
    cache_key = INDUSTRY_CHAIN_PROMPT_SPEC.cache_key(
        "user",
        user_id,
        name,
        resolved_scope.model_dump_json(),
    )
    cached = cache.get(cache_key)
    if cached is not None:
        cached_result = cached if isinstance(cached, IndustryChainResult) else IndustryChainResult.model_validate(cached)
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
            await progress.emit(_event(
                event_type="agent_event",
                stage=_RESEARCH_STAGE,
                message="",
                agent_event=event,
            ))

        outcomes = await asyncio.gather(
            _research_industry_chain(
                name,
                settings=settings,
                scope=resolved_scope,
                event_callback=emit_agent_event if progress_callback is not None else None,
            ),
            _collect_public_industry_data(name),
            return_exceptions=True,
        )
        research_outcome = cast(AgenticResearchResult | Exception, outcomes[0])
        public_outcome = cast(dict[str, Any] | Exception, outcomes[1])

        warnings: list[str] = []
        public_data: dict[str, Any] = {}
        if isinstance(public_outcome, Exception):
            logger.warning("产业链公共数据采集失败: name=%s, error=%s", name, public_outcome)
            _add_warning(warnings, "公共结构化数据采集失败，本次报告仅使用 Agent 工具证据")
        elif isinstance(public_outcome, dict) and _has_public_data(public_outcome):
            public_data = public_outcome
        else:
            _add_warning(warnings, "公共结构化数据未返回有效内容，本次报告仅使用 Agent 工具证据")

        fallback_research = False
        research_evidence: tuple[AgentEvidence, ...] = ()
        evidence_stats = None
        if isinstance(research_outcome, AgentEvidenceInsufficientError):
            if not public_data:
                raise research_outcome
            fallback_research = True
            logger.warning("产业链 Agent 证据不足，使用公共数据兜底: name=%s, error=%s", name, research_outcome)
            _add_warning(warnings, "Agent 证据覆盖不足，已使用公共数据兜底生成降级报告")
            research_context = {
                "agent_summary": "Agent 调研证据不足，以下报告主要基于公共结构化数据。",
                "agent_evidence": "暂无可用 Agent 工具证据",
            }
        elif isinstance(research_outcome, Exception):
            raise research_outcome
        else:
            research_evidence = research_outcome.evidence
            _, rendered_evidence, evidence_stats = compact_industry_evidence(
                research_evidence
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

        compacted_public_data = compact_public_industry_data(public_data) if public_data else {}
        public_serialized = (
            serialize_result(compacted_public_data, _MAX_PUBLIC_CONTEXT_LENGTH)
            if public_data
            else "暂无可用公共结构化数据"
        )
        all_evidence = list(research_evidence)
        public_evidence_id = ""
        if public_data:
            public_evidence = AgentEvidence(
                tool_call_id="public-industry-data",
                tool_name="public_industry_data",
                arguments=f'{{"name":{json.dumps(name, ensure_ascii=False)}}}',
                content=public_serialized,
            )
            public_evidence_id = agent_evidence_id(public_evidence)
            all_evidence.append(public_evidence)
        evidence_catalog = build_evidence_catalog(all_evidence)
        if evidence_stats is None:
            evidence_stats = IndustryChainEvidenceStats()
        if public_data:
            evidence_stats = evidence_stats.model_copy(update={
                "total_count": evidence_stats.total_count + 1,
                "unique_count": evidence_stats.unique_count + 1,
                "selected_count": evidence_stats.selected_count + 1,
                "omitted_count": evidence_stats.omitted_count,
                "prompt_characters": evidence_stats.prompt_characters + len(public_serialized),
            })
        evidence_compaction_note = (
            f"共 {evidence_stats.total_count} 次工具/公共数据调用，去重后 {evidence_stats.unique_count} 条，"
            f"最终向合成模型提供 {evidence_stats.selected_count} 条，省略 {evidence_stats.omitted_count} 条。"
        )

        prompt_context = {
            "name": name,
            "research_scope": render_industry_chain_scope(resolved_scope),
            **research_context,
            "public_data": public_serialized,
            "public_evidence_id": public_evidence_id,
            "company_scope": resolved_scope.company_scope,
            "evidence_compaction_note": evidence_compaction_note,
        }
        await progress.emit(_event(
            event_type="stage_started",
            stage=_SYNTHESIS_STAGE,
            message="AI 正在生成结构化产业链报告...",
        ))
        result: IndustryChainResult
        structured_prompt_succeeded = False
        try:
            prompt_run = await run_structured_prompt(
                INDUSTRY_CHAIN_PROMPT_SPEC,
                prompt_context,
            )
            result = _result_from_payload(name, prompt_run.value.model_dump())
            structured_prompt_succeeded = True
            result.prompt_trace = prompt_run.trace
            result.warnings.extend(warnings)
            if fallback_research:
                result.quality_status = "degraded"
        except PromptExecutionError as prompt_exc:
            result = IndustryChainResult(name=name, schema_version=7, quality_status="degraded")
            result.prompt_trace = prompt_exc.trace
            result.warnings.extend(warnings)
            _add_warning(result.warnings, "结构化报告生成失败，当前仅展示恢复出的降级内容")
            result.missing_evidence.append("结构化报告输出未通过校验，请重新分析")
            result.llm_review = render_industry_markdown(result)
            logger.warning("产业链 Prompt 校验失败，生成确定性降级报告, name=%s", name)

        result.research_scope = resolved_scope.model_dump(mode="json", exclude_none=True)
        result.evidence_catalog = evidence_catalog
        result.evidence_stats = evidence_stats
        unknown_evidence_ids = validate_result_evidence_ids(result, evidence_catalog)
        if unknown_evidence_ids:
            result.quality_status = "degraded"
            _add_warning(result.warnings, "报告引用了不存在的工具证据 ID，已自动移除")
        mismatched_source_urls = validate_result_source_urls(result, evidence_catalog)
        if mismatched_source_urls:
            result.quality_status = "degraded"
            _add_warning(result.warnings, "部分来源链接不属于所引用的工具证据，已自动移除")
        _apply_quality_gate(result)
        if structured_prompt_succeeded:
            result.llm_review = render_industry_markdown(result)
        await progress.emit(_event(
            event_type="stage_completed",
            stage=_SYNTHESIS_STAGE,
            message="结构化产业链报告生成完成",
        ))

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

        if result.archive_status == "saved":
            await auto_mine_from_result(result)

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
        await progress.emit(_event(
            event_type="error",
            stage="error",
            message=detail,
        ))
        raise
