"""产业链 HTTP 请求与列表响应模型。"""

from pydantic import BaseModel

from app.domain.industry_chain import IndustryChainResearchScope
from app.modules.industry_chain.events import IndustryChainProgress
from app.modules.industry_chain.models import (
    IndustryChainChart,
    IndustryChainCompetitionGroup,
    IndustryChainEvent,
    IndustryChainInsight,
    IndustryChainMetric,
    IndustryChainNode,
    IndustryChainResult,
    IndustryChainSource,
)

__all__ = [
    "IndustryChainChart",
    "IndustryChainCompetitionGroup",
    "IndustryChainEvent",
    "IndustryChainHistoryItem",
    "IndustryChainInsight",
    "IndustryChainLatestResponse",
    "IndustryChainResearchScope",
    "IndustryChainMetric",
    "IndustryChainNode",
    "IndustryChainProgress",
    "IndustryChainResult",
    "IndustryChainSource",
]


class IndustryChainHistoryItem(BaseModel):
    """Purpose: 产业链分析历史列表的单条摘要。"""
    name: str
    archive_id: str
    saved_at: str = ""
    title: str = ""
    summary: str = ""
    can_delete: bool


class IndustryChainLatestResponse(BaseModel):
    archive_id: str
    saved_at: str = ""
