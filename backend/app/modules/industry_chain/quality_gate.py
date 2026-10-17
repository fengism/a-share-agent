"""Deterministic industry report quality checks, independent of orchestration."""

from __future__ import annotations

from app.core.market import is_a_share_code
from app.domain.industry_chain import IndustryChainResearchScope
from app.modules.industry_chain.models import IndustryChainResult


def add_warning(warnings: list[str], warning: str) -> None:
    if warning and warning not in warnings:
        warnings.append(warning)


def add_missing_evidence(result: IndustryChainResult, message: str) -> None:
    if message and message not in result.missing_evidence:
        result.missing_evidence.append(message)


def segment_is_covered(segment: str, actual_text: str) -> bool:
    normalized_actual = "".join(char.lower() for char in actual_text if char.isalnum())
    candidates = [segment]
    for separator in ("（", "(", "、", "/", "与", "及"):
        candidates = [part for value in candidates for part in value.split(separator)]
    normalized = ["".join(char.lower() for char in value if char.isalnum()) for value in candidates]
    return any(len(value) >= 2 and value in normalized_actual for value in normalized)


def apply_quality_gate(
    result: IndustryChainResult,
    scope: IndustryChainResearchScope | None = None,
    expected_segments: dict[str, list[str]] | None = None,
) -> None:
    missing: list[str] = []
    if not result.research_theses:
        result.quality_status = "degraded"
        add_missing_evidence(result, "未形成有事实前提、传导机制与反证条件的核心研究判断")
    for thesis in result.research_theses:
        if (
            not thesis.mechanism
            or not thesis.conditions
            or not thesis.counter_evidence
            or not thesis.invalidation
            or not thesis.tracking_metrics
        ):
            result.quality_status = "degraded"
            add_missing_evidence(result, f"核心判断「{thesis.title}」缺少机制、反向证据说明、成立/失效条件或跟踪指标")
    if not result.summary.strip():
        missing.append("核心摘要")
    if not (result.upstream or result.midstream or result.downstream):
        missing.append("产业链节点")
    if not result.sources:
        missing.append("可追溯来源")
    if missing:
        result.quality_status = "degraded"
        add_warning(result.warnings, f"报告结构不完整，缺少：{'、'.join(missing)}")
    missing_core_coverage = [
        label
        for field, label in (("market", "市场"), ("chain", "产业链"), ("companies", "公司"))
        if getattr(result.coverage, field) == "missing"
    ]
    if missing_core_coverage:
        result.quality_status = "degraded"
        add_warning(result.warnings, f"核心研究维度证据缺失：{'、'.join(missing_core_coverage)}")
    if result.conflicts:
        add_warning(result.warnings, f"存在 {len(result.conflicts)} 组数据口径冲突，请结合证据目录核对")
    if result.evidence_catalog and result.summary.strip() and not result.summary_evidence_ids:
        result.quality_status = "degraded"
        add_warning(result.warnings, "核心摘要尚未关联到具体工具证据 ID")

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
        add_warning(result.warnings, f"产业链环节缺失：{'、'.join(missing_tiers)}")

    if expected_segments:
        for tier, label in (("upstream", "上游"), ("midstream", "中游"), ("downstream", "下游")):
            expected = expected_segments.get(tier, [])
            if len(expected) < 2:
                continue
            actual_text = " ".join(
                " ".join(filter(None, (node.name, node.role, node.description))) for node in getattr(result, tier)
            )
            covered = [segment for segment in expected if segment_is_covered(segment, actual_text)]
            if len(covered) * 2 < len(expected):
                missing_names = [segment for segment in expected if segment not in covered]
                result.quality_status = "degraded"
                if result.coverage.chain == "complete":
                    result.coverage.chain = "partial"
                add_missing_evidence(
                    result,
                    f"{label}环节覆盖不足：知识库参考 {len(expected)} 个环节，本次明确覆盖 {len(covered)} 个；"
                    f"待核验 {'、'.join(missing_names[:6])}",
                )

    if scope is not None and scope.company_scope == "a_share":
        invalid_key_stocks = [item for item in result.key_stocks if item.code and not is_a_share_code(item.code)]
        if invalid_key_stocks:
            result.key_stocks = [item for item in result.key_stocks if item not in invalid_key_stocks]
            result.quality_status = "degraded"
            add_warning(result.warnings, "重点公司包含无法确认的 A 股代码，已从结果中移除")

    density_gaps: list[str] = []
    if not result.market_metrics:
        density_gaps.append("缺少与核心判断相关、含统计口径的市场指标")
    if not result.key_stocks:
        density_gaps.append("缺少有业务依据的代表公司研究")
    if not result.driver_insights:
        density_gaps.append("缺少有事实前提的经营驱动分析")
    if not result.risk_insights:
        density_gaps.append("缺少风险触发条件与反向证据分析")
    has_body_evidence = any(
        item.status == "success"
        and item.tool_name in {"web_fetch", "fetch_urls", "read_pdf"}
        and bool(item.content_preview.strip())
        and bool(item.source_urls)
        for item in result.evidence_catalog
    )
    if result.evidence_catalog and not has_body_evidence:
        density_gaps.append("关键结论需要至少 1 条可追溯的网页正文证据")
    if density_gaps:
        result.quality_status = "degraded"
        for gap in density_gaps:
            add_missing_evidence(result, gap)
        add_warning(result.warnings, f"报告研究依据不足，仍有 {len(density_gaps)} 项待补充")

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
        add_warning(result.warnings, "多数结构化结论缺少可点击的原始来源链接")
    evidence_linked_items = [item for item in sourced_items if bool(getattr(item, "evidence_ids", []))]
    if result.evidence_catalog and len(sourced_items) >= 2 and len(evidence_linked_items) * 2 < len(sourced_items):
        result.quality_status = "degraded"
        add_warning(result.warnings, "多数结构化结论尚未关联到具体工具证据 ID")
