"""Build bounded public evidence and truthful evidence/source metrics."""

from __future__ import annotations

import json
from typing import Any

from app.agentic.contracts import AgentEvidence, agent_evidence_id
from app.agentic.tools.serialization import serialize_result

PUBLIC_DATA_KEYS = (
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
MAX_PUBLIC_CONTEXT_LENGTH = 20_000


def has_meaningful_value(value: Any) -> bool:
    if value is None or isinstance(value, Exception):
        return False
    if isinstance(value, dict):
        if value.get("error"):
            return False
        return any(has_meaningful_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(has_meaningful_value(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def has_public_data(value: Any) -> bool:
    return isinstance(value, dict) and any(has_meaningful_value(value.get(key)) for key in PUBLIC_DATA_KEYS)


def collection_item_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(collection_item_count(item) for item in value.values())
    return 0


def evidence_inventory(public_data: dict[str, Any], *, agent_evidence_count: int) -> str:
    public_counts = "；".join(
        f"{key} {collection_item_count(public_data.get(key))} 条"
        for key in PUBLIC_DATA_KEYS
    )
    return f"Agent 工具证据 {agent_evidence_count} 条；{public_counts}"


def public_evidence_items(name: str, public_data: dict[str, Any]) -> list[AgentEvidence]:
    """Split public structured data by dimension so claims cite a bounded source."""
    items: list[AgentEvidence] = []
    for key in PUBLIC_DATA_KEYS:
        value = public_data.get(key)
        if not has_meaningful_value(value):
            continue
        items.append(AgentEvidence(
            tool_call_id=f"public-industry-data:{key}",
            tool_name="public_industry_data",
            arguments=json.dumps({"name": name, "dimension": key}, ensure_ascii=False, separators=(",", ":")),
            content=serialize_result({key: value}, MAX_PUBLIC_CONTEXT_LENGTH // 2),
        ))
    return items


def public_evidence_reference(items: list[AgentEvidence]) -> str:
    return "；".join(
        f"{json.loads(item.arguments)['dimension']}={agent_evidence_id(item)}"
        for item in items
    )


def independent_source_count(evidence_catalog) -> int:
    urls = {
        url.rstrip("/")
        for item in evidence_catalog
        if item.status == "success"
        for url in item.source_urls
        if url
    }
    return len(urls)


def usable_agent_evidence_count(evidence: list[AgentEvidence]) -> int:
    return len({
        agent_evidence_id(item)
        for item in evidence
        if item.tool_name != "public_industry_data"
        and item.evidence_state.usable_acquisition
    })
