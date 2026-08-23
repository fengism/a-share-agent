"""每日潜力股挖掘 HTTP API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.auth.dependencies import require_active_user
from app.domain.identity import AuthenticatedUser
from app.modules.potential.public import (
    PotentialDailyResult,
    get_potential_result,
    list_potential_date_items,
    run_daily_mining,
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


@router.post("/run", response_model=PotentialDailyResult | None)
async def trigger_potential_mining(
    force: Annotated[bool, Query(description="当天已有结果时是否强制重跑")] = False,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """手动触发一次潜力股挖掘（后台每日任务之外的即时入口）。"""
    return await run_daily_mining(force=force)
