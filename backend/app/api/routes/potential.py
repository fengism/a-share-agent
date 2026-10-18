"""每日潜力股挖掘 HTTP API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.auth.dependencies import require_active_user
from app.domain.identity import AuthenticatedUser
from app.modules.potential.public import (
    PotentialDailyResult,
    PotentialPerformanceSummary,
    PotentialRunStatus,
    compute_potential_performance,
    get_potential_result,
    list_potential_date_items,
    mining_run_status,
    start_daily_mining_background,
)

router = APIRouter()


@router.get("/latest", response_model=PotentialDailyResult | None)
async def get_latest_potential(
    date: Annotated[str | None, Query(description="日期 YYYY-MM-DD，缺省取最近一份")] = None,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """获取最近（或指定日期）的潜力股挖掘结果。"""
    return await get_potential_result(date)


@router.get("/dates")
async def get_potential_dates(
    limit: Annotated[int, Query(ge=1, le=90)] = 30,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """列出可用结果的日期索引。"""
    return await list_potential_date_items(limit)


@router.get("/performance", response_model=PotentialPerformanceSummary | None)
async def get_potential_performance(
    date: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$", description="挖掘日期 YYYY-MM-DD")],
    days: Annotated[int, Query(ge=1, le=30, description="持有交易日数")] = 5,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """计算某个挖掘日期在指定持有期内的前瞻表现。"""
    return await compute_potential_performance(date, days)


@router.post("/run", response_model=PotentialRunStatus)
async def trigger_potential_mining(
    force: Annotated[bool, Query(description="当天已有结果时是否强制重跑")] = False,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """后台触发一次潜力股挖掘并立即返回任务状态，避免 HTTP 长阻塞。"""
    return await start_daily_mining_background(force=force)


@router.get("/run/status", response_model=PotentialRunStatus)
async def get_potential_run_status(
    user: AuthenticatedUser = Depends(require_active_user),
):
    """查询手动挖掘任务状态，供前端轮询。"""
    return mining_run_status()
