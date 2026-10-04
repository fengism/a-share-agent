"""概念板块联动 API：概念选择、成分股（含行情）与本地合成指数。"""

from fastapi import APIRouter, Query

from app.financial_data.market.public import (
    get_concept_constituents as get_concept_constituents_service,
)
from app.financial_data.market.public import (
    get_concept_index as get_concept_index_service,
)
from app.financial_data.market.public import list_concepts as list_concepts_service
from app.financial_data.market.quotes.schemas import (
    ConceptConstituentResponse,
    ConceptIndexResponse,
    ConceptListResponse,
    ConceptSummaryItem,
)

router = APIRouter()


@router.get("/concepts", response_model=ConceptListResponse)
def list_concepts(
    query: str = Query(default="", max_length=64, description="概念名称模糊搜索"),
    limit: int = Query(default=200, ge=1, le=2000),
):
    """获取概念列表，按成分股只数降序，用于概念选择器。"""
    items = list_concepts_service(query=query, limit=limit)
    return ConceptListResponse(
        items=[ConceptSummaryItem(name=item.name, stock_count=item.stock_count) for item in items],
        total=len(items),
    )


@router.get("/concept/{concept}/constituents", response_model=ConceptConstituentResponse)
async def get_concept_constituents(concept: str):
    """获取概念成分股及其实时行情；每只股票带全部所属概念用于反向联动。"""
    return await get_concept_constituents_service(concept)


@router.get("/concept/{concept}/index", response_model=ConceptIndexResponse)
async def get_concept_index(
    concept: str,
    days: int = Query(default=365, ge=30, le=3650, description="回溯自然日天数，上限 10 年"),
):
    """获取本地合成的等权概念指数（成分股前复权日线链式复利）。"""
    return await get_concept_index_service(concept, days=days)
