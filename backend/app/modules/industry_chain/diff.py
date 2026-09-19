"""产业链报告版本差异计算。"""

import json
from collections.abc import Callable, Iterable
from typing import Any

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
    category: str,
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


def compute_industry_chain_changes(
    previous: IndustryChainResult | None,
    current: IndustryChainResult,
    *,
    previous_archive_id: str = "",
) -> IndustryChainChangeSet:
    """对比前后两版报告，生成可展示、可持久化的结构化变化摘要。"""
    if previous is None:
        return IndustryChainChangeSet(previous_archive_id=previous_archive_id)

    items: list[IndustryChainChangeItem] = []
    for label, old_nodes, new_nodes in (
        ("上游", previous.upstream, current.upstream),
        ("中游", previous.midstream, current.midstream),
        ("下游", previous.downstream, current.downstream),
    ):
        _append_collection_changes(
            items,
            category="chain",
            previous=old_nodes,
            current=new_nodes,
            key=_node_key,
            title=lambda node, prefix=label: f"{prefix} · {_node_title(node)}",
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
    _append_collection_changes(
        items,
        category="market",
        previous=previous.market_metrics,
        current=current.market_metrics,
        key=lambda metric: metric.label.strip().lower(),
        title=lambda metric: metric.label,
        detail=_metric_detail,
    )
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

    return IndustryChainChangeSet(
        previous_archive_id=previous_archive_id or previous.archive_id,
        has_changes=bool(items),
        added_count=sum(item.change_type == "added" for item in items),
        removed_count=sum(item.change_type == "removed" for item in items),
        updated_count=sum(item.change_type == "updated" for item in items),
        items=items,
    )


__all__ = ["compute_industry_chain_changes"]
