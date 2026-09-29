"""从工具返回的显式字段提取来源/时效；未知项保留未知，不以生成时间代替数据日期。"""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvidenceFreshness(BaseModel):
    tool_name: str
    evidence_id: str
    sources: list[str] = Field(default_factory=list)
    data_dates: list[str] = Field(default_factory=list)
    report_periods: list[str] = Field(default_factory=list)
    cache_status: str = "unknown"


class AnalysisProvenance(BaseModel):
    research_started_at: str
    research_completed_at: str
    report_regenerated: bool = False
    freshness_note: str = "重新生成仅跳过分析报告缓存；工具可能使用各自缓存。未披露的日期与缓存状态均为未知。"
    evidence: list[EvidenceFreshness] = Field(default_factory=list)


def build_provenance(research: Any, *, started_at: datetime, completed_at: datetime, force: bool) -> AnalysisProvenance:
    items = []
    for evidence in research.evidence:
        if evidence.is_error:
            continue
        sources: set[str] = set()
        dates: set[str] = set()
        periods: set[str] = set()
        states: set[str] = set()
        nodes = 0

        def walk(value: Any, depth: int = 0) -> None:
            nonlocal nodes
            nodes += 1
            if depth > 6 or nodes > 1000:
                return
            if isinstance(value, list):
                for child in value[:100]:
                    walk(child, depth + 1)
            elif isinstance(value, dict):
                for key, child in value.items():
                    scalar = isinstance(child, (str, int, float)) and not isinstance(child, bool)
                    text = str(child).strip()[:256] if scalar else ""
                    if key in {"source", "source_name", "url", "source_url"} and text:
                        sources.add(text)
                    elif key in {"as_of_date", "data_date", "trade_date", "date", "published_at", "fetched_at", "updated_at"} and text:
                        dates.add(f"{key}: {text}")
                    elif key in {"report_period", "report_date", "period_end", "报告期"} and text:
                        periods.add(f"{key}: {text}")
                    elif key in {"cached", "cache_hit", "from_cache"} and isinstance(child, bool):
                        states.add("cached" if child else "live")
                    elif key in {"stale", "is_stale"} and child is True:
                        states.add("stale")
                    walk(child, depth + 1)
        try:
            walk(json.loads(evidence.content))
        except (ValueError, TypeError):
            pass
        status = "stale" if "stale" in states else (next(iter(states)) if len(states) == 1 else "mixed" if states else "unknown")
        items.append(EvidenceFreshness(
            tool_name=evidence.tool_name, evidence_id=evidence.tool_call_id,
            sources=sorted(sources)[:8], data_dates=sorted(dates)[-12:], report_periods=sorted(periods)[-8:], cache_status=status,
        ))
    return AnalysisProvenance(
        research_started_at=started_at.isoformat(), research_completed_at=completed_at.isoformat(),
        report_regenerated=force, evidence=items,
    )
