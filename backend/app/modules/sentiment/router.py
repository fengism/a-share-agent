"""行业韭菜指数 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.modules.sentiment.schemas import (
    LeekIndexHistoryResponse,
    LeekIndexOverviewResponse,
)
from app.modules.sentiment.service import get_leek_index_service

router = APIRouter()


@router.get(
    "/leek-index/overview",
    response_model=LeekIndexOverviewResponse,
    summary="获取全市场申万一级行业韭菜指数总览",
    description="返回 31 个申万一级行业的散户狂热度、资金剪刀差与套牢风险评分 (0-100)。",
)
async def get_leek_index_overview(
    force_refresh: bool = Query(False, description="是否强制重新计算并忽略缓存"),
) -> LeekIndexOverviewResponse:
    service = get_leek_index_service()
    return await service.get_overview(force_refresh=force_refresh)


@router.get(
    "/leek-index/{industry_name}/history",
    response_model=LeekIndexHistoryResponse,
    summary="获取指定行业的历史韭菜指数时序",
    description="用于前端绘制行业走势与散户韭菜指数双轴对照图。",
)
async def get_industry_leek_history(
    industry_name: str,
    days: int = Query(30, ge=5, le=180, description="历史天数"),
) -> LeekIndexHistoryResponse:
    service = get_leek_index_service()
    return await service.get_history(industry_name=industry_name, days=days)


@router.post(
    "/leek-index/refresh",
    response_model=LeekIndexOverviewResponse,
    summary="手动触发全市场韭菜指数刷新与持久化归档",
)
async def refresh_leek_index() -> LeekIndexOverviewResponse:
    service = get_leek_index_service()
    return await service.get_overview(force_refresh=True)
