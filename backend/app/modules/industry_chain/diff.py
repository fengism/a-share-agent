"""产业链报告版本差异计算。"""

import json
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from decimal import localcontext
from typing import Any, Literal

from pydantic import BaseModel

from app.modules.industry_chain.models import (
    IndustryChainChangeItem,
    IndustryChainChangeSet,
    IndustryChainEvent,
    IndustryChainInsight,
    IndustryChainMetric,
    IndustryChainNode,
    IndustryChainResult,
)
from app.modules.industry_chain.numbers import parse_number


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, list):
        return "、".join(filter(None, (_text(item) for item in value)))
    return str(value).strip()


def _node_key(node: IndustryChainNode) -> str:
    return (node.code or node.name or node.company or "").strip().lower()


def _node_title(node: IndustryChainNode) -> str:
    return (node.name or node.company or node.code or "未命名节点").strip()


def _node_detail(node: IndustryChainNode) -> str:
    return "；".join(
        part
        for part in (
            node.role,
            node.description,
            f"代表企业：{'、'.join(node.companies)}" if node.companies else "",
            f"市场份额：{node.market_share}" if node.market_share else "",
            node.metric,
        )
        if part
    )


def _metric_detail(metric: IndustryChainMetric) -> str:
    return " · ".join(part for part in (metric.value, metric.period, metric.growth) if part)


def _insight_detail(insight: IndustryChainInsight) -> str:
    return insight.detail or insight.evidence or insight.title


def _event_detail(event: IndustryChainEvent) -> str:
    return " · ".join(part for part in (event.date, event.impact) if part)


def _append_collection_changes(
    changes: list[IndustryChainChangeItem],
    *,
    category: Literal["chain", "company", "market", "event", "driver", "risk", "summary"],
    previous: Iterable[Any],
    current: Iterable[Any],
    key: Callable[[Any], str],
    title: Callable[[Any], str],
    detail: Callable[[Any], str],
) -> None:
    before = {key(item): item for item in previous if key(item)}
    after = {key(item): item for item in current if key(item)}
    for item_key in sorted(after.keys() - before.keys()):
        item = after[item_key]
        changes.append(IndustryChainChangeItem(
            category=category,
            change_type="added",
            title=title(item),
            after=detail(item),
        ))
    for item_key in sorted(before.keys() - after.keys()):
        item = before[item_key]
        changes.append(IndustryChainChangeItem(
            category=category,
            change_type="removed",
            title=title(item),
            before=detail(item),
        ))
    for item_key in sorted(before.keys() & after.keys()):
        old_item = before[item_key]
        new_item = after[item_key]
        old_detail = detail(old_item)
        new_detail = detail(new_item)
        if old_detail != new_detail:
            changes.append(IndustryChainChangeItem(
                category=category,
                change_type="updated",
                title=title(new_item),
                before=old_detail,
                after=new_detail,
            ))


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _metric_context(metric: IndustryChainMetric) -> str:
    return " · ".join(part or "口径缺失" for part in (
        metric.value, metric.period, metric.unit, metric.region, metric.statistical_scope,
    ))


def _append_metric_pair(
    items: list[IndustryChainChangeItem], old: IndustryChainMetric, new: IndustryChainMetric,
) -> None:
    fields = ("unit", "region", "statistical_scope", "period")
    same_scope = all(getattr(old, field) and _normalized(getattr(old, field)) == _normalized(getattr(new, field)) for field in fields)
    old_number, new_number = parse_number(old.numeric_value), parse_number(new.numeric_value)
    verified = old.verification_status == new.verification_status == "quote_matched"
    title = f"{new.label}（{new.region or '地域缺失'} · {new.period or '统计期缺失'}）"
    if same_scope and verified and old_number is not None and new_number is not None:
        if old_number != new_number:
            with localcontext() as context:
                context.prec = 150
                delta = new_number - old_number
                percentage = delta / abs(old_number) * 100 if old_number else None
            items.append(IndustryChainChangeItem(
                category="market", change_type="updated", title=title, change_basis="fact",
                before=_metric_context(old), after=_metric_context(new),
                numeric_delta=format(delta, "f"), percentage_delta=f"{percentage:.2f}%" if percentage is not None else "",
                detail=f"同统计期、同口径数值修订；单位：{new.unit}。不自动推断投资判断变化。",
            ))
        elif set(old.evidence_ids) != set(new.evidence_ids):
            items.append(IndustryChainChangeItem(category="market", change_type="updated", title=title,
                change_basis="evidence", detail="指标数值未变，来源证据发生更新。"))
        elif old.growth != new.growth:
            items.append(IndustryChainChangeItem(category="market", change_type="updated", title=title,
                change_basis="text", before=old.growth, after=new.growth, detail="增长描述更新，未独立核验。"))
    elif _metric_context(old) != _metric_context(new) or old.growth != new.growth:
        items.append(IndustryChainChangeItem(category="market", change_type="updated", title=title,
            change_basis="observation" if not same_scope else "text",
            before=_metric_context(old), after=_metric_context(new),
            detail="统计期/口径变化或数值未核验，不计算涨跌幅。"))
    elif set(old.evidence_ids) != set(new.evidence_ids):
        items.append(IndustryChainChangeItem(category="market", change_type="updated", title=title,
            change_basis="evidence", detail="指标值未变，来源证据发生更新。"))


def _append_metric_changes(
    items: list[IndustryChainChangeItem],
    previous: IndustryChainResult,
    current: IndustryChainResult,
) -> None:
    def group(metrics: list[IndustryChainMetric]):
        grouped: dict[str, dict[tuple[str, ...], list[IndustryChainMetric]]] = defaultdict(lambda: defaultdict(list))
        for metric in metrics:
            identity = _normalized(metric.metric_id or metric.label)
            context = tuple(_normalized(getattr(metric, field)) for field in ("unit", "region", "statistical_scope", "period"))
            grouped[identity][context].append(metric)
        return grouped

    before, after = group(previous.market_metrics), group(current.market_metrics)
    for identity in sorted(before.keys() | after.keys()):
        old_group, new_group = before.get(identity, {}), after.get(identity, {})
        for context in sorted(old_group.keys() & new_group.keys()):
            olds, news = old_group[context], new_group[context]
            if len(olds) == len(news) == 1:
                _append_metric_pair(items, olds[0], news[0])
            else:
                # Duplicate rows are not changes by themselves. Only surface differing observations.
                def signatures(rows: list[IndustryChainMetric]):
                    return sorted((row.value, row.numeric_value, row.growth) for row in rows)
                if signatures(olds) != signatures(news):
                    items.append(IndustryChainChangeItem(category="market", change_type="updated",
                        title=f"{news[0].label}：同口径重复记录", change_basis="observation",
                        detail="同一统计口径存在多条记录且内容变化，未计算数值差异。"))
        old_unmatched = [row for context, rows in old_group.items() if context not in new_group for row in rows]
        new_unmatched = [row for context, rows in new_group.items() if context not in old_group for row in rows]
        if len(old_unmatched) == len(new_unmatched) == 1:
            _append_metric_pair(items, old_unmatched[0], new_unmatched[0])
            continue
        for change, rows in (("removed", old_unmatched), ("added", new_unmatched)):
            for row in rows:
                items.append(IndustryChainChangeItem.model_validate({
                    "category": "market", "change_type": change,
                    "title": f"{row.label}（{row.region or '地域缺失'} · {row.period or '统计期缺失'}）",
                    "change_basis": "observation",
                    "before": _metric_context(row) if change == "removed" else "",
                    "after": _metric_context(row) if change == "added" else "",
                    "detail": "报告观测项变化，不代表行业事实新增或消失。",
                }))


def compute_industry_chain_changes(
    previous: IndustryChainResult | None,
    current: IndustryChainResult,
    *,
    previous_archive_id: str = "",
) -> IndustryChainChangeSet:
    """对比前后两版报告，生成可展示、可持久化的结构化变化摘要。"""
    if previous is None:
        return IndustryChainChangeSet(previous_archive_id=previous_archive_id)

    scope_fields = ["region", "company_scope", "time_range"]
    if previous.research_scope.get("time_range") == "custom" or current.research_scope.get("time_range") == "custom":
        scope_fields += ["start_date", "end_date"]
    changed_scope = [field for field in scope_fields if previous.research_scope.get(field) != current.research_scope.get(field)]
    if changed_scope or bool(previous.research_scope) != bool(current.research_scope):
        return IndustryChainChangeSet(
            previous_archive_id=previous_archive_id or previous.archive_id,
            comparable=False,
            comparison_note="研究地域、公司范围或时间窗口不同，不进行直接比较。",
        )
    if any(not report.research_scope.get(field) for report in (previous, current) for field in scope_fields):
        return IndustryChainChangeSet(
            previous_archive_id=previous_archive_id or previous.archive_id,
            comparable=False, comparison_note="历史报告缺少研究范围，无法确认口径一致。",
        )
    items: list[IndustryChainChangeItem] = []
    for label, old_nodes, new_nodes in (
        ("上游", previous.upstream, current.upstream),
        ("中游", previous.midstream, current.midstream),
        ("下游", previous.downstream, current.downstream),
    ):
        def tier_title(node: IndustryChainNode) -> str:
            return f"{label} · {_node_title(node)}"

        _append_collection_changes(
            items,
            category="chain",
            previous=old_nodes,
            current=new_nodes,
            key=_node_key,
            title=tier_title,
            detail=_node_detail,
        )
    _append_collection_changes(
        items,
        category="company",
        previous=previous.key_stocks,
        current=current.key_stocks,
        key=_node_key,
        title=_node_title,
        detail=_node_detail,
    )
    _append_metric_changes(items, previous, current)
    _append_collection_changes(
        items,
        category="event",
        previous=previous.key_events,
        current=current.key_events,
        key=lambda event: event.title.strip().lower(),
        title=lambda event: event.title,
        detail=_event_detail,
    )

    previous_drivers = previous.driver_insights or [IndustryChainInsight(title=item) for item in previous.drivers]
    current_drivers = current.driver_insights or [IndustryChainInsight(title=item) for item in current.drivers]
    _append_collection_changes(
        items,
        category="driver",
        previous=previous_drivers,
        current=current_drivers,
        key=lambda insight: insight.title.strip().lower(),
        title=lambda insight: insight.title,
        detail=_insight_detail,
    )
    previous_risks = previous.risk_insights or [IndustryChainInsight(title=item) for item in previous.risks]
    current_risks = current.risk_insights or [IndustryChainInsight(title=item) for item in current.risks]
    _append_collection_changes(
        items,
        category="risk",
        previous=previous_risks,
        current=current_risks,
        key=lambda insight: insight.title.strip().lower(),
        title=lambda insight: insight.title,
        detail=_insight_detail,
    )

    if _text(previous.summary) != _text(current.summary):
        items.append(IndustryChainChangeItem(
            category="summary",
            change_type="updated",
            title="核心结论更新",
            before=previous.summary,
            after=current.summary,
        ))
    if _text(previous.positioning) != _text(current.positioning):
        items.append(IndustryChainChangeItem(
            category="summary",
            change_type="updated",
            title="产业定位更新",
            before=previous.positioning,
            after=current.positioning,
        ))

    priority = {"fact": 0, "observation": 1, "evidence": 2, "text": 3}
    items.sort(key=lambda item: priority[item.change_basis])
    return IndustryChainChangeSet(
        previous_archive_id=previous_archive_id or previous.archive_id,
        comparison_note="数值变化仅比较同口径指标；统计期变化单独列示。文字更新不代表事实变化或投资判断改变。",
        has_changes=bool(items),
        added_count=sum(item.change_type == "added" for item in items),
        removed_count=sum(item.change_type == "removed" for item in items),
        updated_count=sum(item.change_type == "updated" for item in items),
        items=items,
    )


__all__ = ["compute_industry_chain_changes"]
