import asyncio
import json
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
from app.core.market import is_a_share_code
from app.core.progress import ProgressEmitter
from app.domain.industry_chain import (
    IndustryChainResearchScope,
    render_industry_chain_scope,
    resolve_industry_chain_scope,
)
from app.infrastructure.llm.prompting import PromptExecutionError, run_structured_prompt
from app.modules.industry_chain import research as industry_research
from app.modules.industry_chain.archive_service import (
    get_latest_industry_chain_archive,
    load_industry_chain_archive,
)
from app.modules.industry_chain.atlas.loader import get_atlas_chain, list_atlas_chains
from app.modules.industry_chain.atlas.miner import auto_mine_from_result, mining_slug
from app.modules.industry_chain.diff import compute_industry_chain_changes
from app.modules.industry_chain.events import IndustryChainProgress
from app.modules.industry_chain.evidence import (
    build_evidence_catalog,
    compact_industry_evidence,
    compact_public_industry_data,
    validate_result_evidence_ids,
    validate_result_source_urls,
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
from app.modules.industry_chain.report_renderer import render_industry_markdown

logger = logging.getLogger(__name__)

_research_industry_chain: Callable[..., Awaitable[AgenticResearchResult]] = industry_research.research_industry_chain
_collect_public_industry_data: Callable[..., Awaitable[dict[str, Any]]] = collect_public_industry_data
_result_from_payload: Callable[[str, dict[str, Any]], IndustryChainResult] = result_from_payload

_RESEARCH_STAGE = "research"
_SYNTHESIS_STAGE = "synthesis"
_MAX_PUBLIC_CONTEXT_LENGTH = 20_000
_RESULT_CACHE_TTL_SECONDS = 24 * 60 * 60
_PUBLIC_DATA_KEYS = (
    "stocks",
    "market_data",
    "competition_data",
    "technology_data",
    "chain_data",
    "driver_risk_data",
    "reports",
    "events",
    "rankings",
)


def _has_meaningful_value(value: Any) -> bool:
    if value is None or isinstance(value, Exception):
        return False
    if isinstance(value, dict):
        if value.get("error"):
            return False
        return any(_has_meaningful_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_meaningful_value(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _has_public_data(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return any(_has_meaningful_value(value.get(key)) for key in _PUBLIC_DATA_KEYS)


def _add_warning(warnings: list[str], warning: str) -> None:
    if warning and warning not in warnings:
        warnings.append(warning)


def _add_missing_evidence(result: IndustryChainResult, message: str) -> None:
    if message and message not in result.missing_evidence:
        result.missing_evidence.append(message)


def _collection_item_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(_collection_item_count(item) for item in value.values())
    return 0


def _evidence_inventory(
    public_data: dict[str, Any],
    *,
    agent_evidence_count: int,
) -> str:
    public_counts = "；".join(
        f"{key} {_collection_item_count(public_data.get(key))} 条"
        for key in _PUBLIC_DATA_KEYS
    )
    return f"Agent 工具证据 {agent_evidence_count} 条；{public_counts}"


def _load_cached_result(cache_key: str, *, force: bool) -> IndustryChainResult | None:
    if force:
        return None
    cached = cache.get(cache_key)
    if cached is None:
        return None
    return cached if isinstance(cached, IndustryChainResult) else IndustryChainResult.model_validate(cached)


def _apply_quality_gate(
    result: IndustryChainResult,
    scope: IndustryChainResearchScope | None = None,
) -> None:
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

    missing_tiers = [
        label
        for nodes, label in (
            (result.upstream, "上游"),
            (result.midstream, "中游"),
            (result.downstream, "下游"),
        )
        if not nodes
    ]
    if missing_tiers and len(missing_tiers) < 3:
        result.quality_status = "degraded"
        if result.coverage.chain == "complete":
            result.coverage.chain = "partial"
        _add_warning(result.warnings, f"产业链环节缺失：{'、'.join(missing_tiers)}")

    if scope is not None and scope.company_scope == "a_share":
        invalid_key_stocks = [
            item
            for item in result.key_stocks
            if item.code and not is_a_share_code(item.code)
        ]
        if invalid_key_stocks:
            result.key_stocks = [
                item for item in result.key_stocks if item not in invalid_key_stocks
            ]
            result.quality_status = "degraded"
            _add_warning(result.warnings, "重点公司包含无法确认的 A 股代码，已从结果中移除")

    density_gaps: list[str] = []
    if result.coverage.market != "missing" and len(result.market_metrics) < 2:
        density_gaps.append("市场研究需要至少 2 项市场指标及对应统计口径")
    covered_tiers = [
        (label, nodes)
        for label, nodes in (
            ("上游", result.upstream),
            ("中游", result.midstream),
            ("下游", result.downstream),
        )
        if nodes
    ]
    if result.coverage.chain != "missing" and any(
        len(nodes) < 2 for _, nodes in covered_tiers
    ):
        sparse_tiers = "、".join(
            label for label, nodes in covered_tiers if len(nodes) < 2
        )
        density_gaps.append(f"产业链每个环节至少 2 个节点，当前不足：{sparse_tiers}")
    if scope is not None and scope.company_scope == "a_share":
        valid_codes = {
            item.code.strip()
            for item in result.key_stocks
            if item.code and is_a_share_code(item.code)
        }
        if len(valid_codes) < 4:
            density_gaps.append("重点公司需要至少 4 家有效 A 股公司及产业链角色证据")
    driver_count = len({
        item.strip()
        for item in [
            *result.drivers,
            *(insight.title for insight in result.driver_insights),
        ]
        if item.strip()
    })
    if driver_count < 2:
        density_gaps.append("驱动因素需要至少 2 项行业驱动及事实依据")
    risk_count = len({
        item.strip()
        for item in [
            *result.risks,
            *(insight.title for insight in result.risk_insights),
        ]
        if item.strip()
    })
    if risk_count < 2:
        density_gaps.append("风险分析需要至少 2 项风险及触发条件")
    if len(result.sources) < 4:
        density_gaps.append("来源目录需要至少 4 条可追溯来源")
    has_body_evidence = any(
        item.status == "success"
        and item.tool_name in {"fetch_url", "fetch_urls"}
        and bool(item.content_preview.strip())
        and bool(item.source_urls)
        for item in result.evidence_catalog
    )
    if result.evidence_catalog and not has_body_evidence:
        density_gaps.append("关键结论需要至少 1 条可追溯的网页正文证据")
    if density_gaps:
        result.quality_status = "degraded"
        for gap in density_gaps:
            _add_missing_evidence(result, gap)
        _add_warning(result.warnings, f"报告证据密度不足，仍有 {len(density_gaps)} 项待补充")

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
    force: bool = False,
) -> IndustryChainResult:
    """执行产业链数据采集、结构化生成和结果存档。"""
    total_started_at = time.perf_counter()
    progress = ProgressEmitter(progress_callback)
    resolved_scope = resolve_industry_chain_scope(scope)
    # 未显式指定日期时，start/end/as_of 随"今天"重算；从缓存键剔除日期字段，
    # 否则 24h 结果缓存跨天必然全量重跑（2 轮 Agent + 1 次合成）
    scope_payload = resolved_scope.model_dump(mode="json")
    if not (scope and (scope.start_date or scope.as_of_date or scope.time_range == "custom")):
        for date_field in ("start_date", "end_date", "as_of_date"):
            scope_payload.pop(date_field, None)
    scope_cache_text = json.dumps(scope_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cache_key = INDUSTRY_CHAIN_PROMPT_SPEC.cache_key(
        "user",
        user_id,
        name,
        scope_cache_text,
    )
    cached_result = _load_cached_result(cache_key, force=force)
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

        research_started_at = time.perf_counter()
        outcomes = await asyncio.gather(
            _research_industry_chain(
                name,
                settings=settings,
                scope=resolved_scope,
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
            research_context = {
                "agent_summary": f"产业链「{name}」调研完成。注意：{research_outcome}。以下分析基于现有可用公开信息综合评估。",
                "agent_evidence": "部分公开证据缺失，已使用可用数据推演。",
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
        research_duration_ms = round((time.perf_counter() - research_started_at) * 1000)

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
        agent_evidence_gaps = (
            "、".join(research_outcome.evidence_gaps)
            if not isinstance(research_outcome, Exception) and research_outcome.evidence_gaps
            else "无"
        )

        prompt_context = {
            "name": name,
            "research_scope": render_industry_chain_scope(resolved_scope),
            "atlas_prior": _build_atlas_prior(name),
            **research_context,
            "public_data": public_serialized,
            "public_evidence_id": public_evidence_id,
            "company_scope": resolved_scope.company_scope,
            "evidence_compaction_note": evidence_compaction_note,
            "agent_evidence_gaps": agent_evidence_gaps,
            "evidence_inventory": _evidence_inventory(
                public_data,
                agent_evidence_count=evidence_stats.selected_count - (1 if public_data else 0),
            ),
        }
        synthesis_started_at = time.perf_counter()
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

        try:
            from app.financial_data.stock.profile.name_map import get_stock_name_map
            name_map = await get_stock_name_map()
            if name_map:
                from app.modules.industry_chain.normalizer import enrich_result_stock_codes
                result = enrich_result_stock_codes(result, name_map)
        except Exception as enrich_exc:
            logger.debug("股票代码自动富化跳过: %s", enrich_exc)

        result.topic_resolution = build_topic_resolution(name, result, public_data)
        result.opportunities = build_opportunities(result)
        _apply_quality_gate(result, resolved_scope)
        if structured_prompt_succeeded:
            result.llm_review = render_industry_markdown(result)
        await progress.emit(_event(
            event_type="stage_completed",
            stage=_SYNTHESIS_STAGE,
            message="结构化产业链报告生成完成",
        ))
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
            cache_hits=metadata_dimensions("cache_hits"),
            cache_misses=metadata_dimensions("cache_misses"),
            failed_dimensions=metadata_dimensions("failed_dimensions"),
            successful_dimensions=metadata_dimensions("successful_dimensions"),
            agent_evidence_count=len(research_evidence),
            public_item_count=public_item_count,
        )

        archive_started_at = time.perf_counter()
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

        result.analysis_metadata.archive_duration_ms = round(
            (time.perf_counter() - archive_started_at) * 1000
        )
        result.analysis_metadata.total_duration_ms = round(
            (time.perf_counter() - total_started_at) * 1000
        )

        if result.archive_status == "saved" and result.quality_status == "complete":
            # 降级报告结构不完整、代码未过全量校验，不写入共享知识库
            await auto_mine_from_result(result)
            cache.set(cache_key, result, ttl=_RESULT_CACHE_TTL_SECONDS)

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


def _build_atlas_prior(name: str) -> str:
    """从知识库查找同名/别名/包含匹配的链条，输出紧凑先验摘要（挖掘结果反哺后续分析）。"""
    normalized = name.strip()
    matched = get_atlas_chain(mining_slug(normalized))
    if matched is None:
        for chain in list_atlas_chains():
            if chain.name == normalized or normalized in (chain.aliases or []):
                matched = chain
                break
    if matched is None and len(normalized) >= 2:
        for chain in list_atlas_chains():
            if (
                normalized in chain.name
                or chain.name in normalized
                or any(normalized in a or a in normalized for a in (chain.aliases or []))
            ):
                matched = chain
                break
    if matched is None:
        return "无"
    lines = [f"知识库链条：{matched.name}（{matched.category}，来源：{matched.source}）"]
    if matched.summary:
        lines.append(f"概要：{matched.summary}")
    for layer in matched.layers:
        segments = "；".join(
            f"{segment.name}（{'、'.join(company.name for company in segment.companies[:4])}）"
            for segment in layer.segments[:6]
        )
        lines.append(f"{layer.name}：{segments}")
    return "\n".join(lines)[:4000]
