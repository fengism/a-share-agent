"""量化研究 API。"""

from fastapi import APIRouter, Depends, Query, status

from app.api.errors import BadRequestError, ConflictError, NotFoundError
from app.modules.auth.public import AuthenticatedUser, require_active_user
from app.modules.quant.schemas import (
    QuantBacktestCreate,
    QuantBacktestList,
    QuantBacktestRun,
    QuantDeleteResponse,
    QuantSavedStrategy,
    QuantStrategyPreset,
    QuantStrategySave,
)
from app.modules.quant.service import (
    cancel_backtest,
    create_backtest,
    delete_backtest,
    delete_user_strategy,
    get_backtest,
    list_backtests,
    list_user_strategies,
    retry_backtest,
    save_user_strategy,
    strategy_presets,
)

router = APIRouter()


@router.get("/strategy-presets", response_model=list[QuantStrategyPreset])
async def get_strategy_presets():
    return strategy_presets()


@router.get("/strategies", response_model=list[QuantSavedStrategy])
async def get_saved_strategies(user: AuthenticatedUser = Depends(require_active_user)):
    return await list_user_strategies(user["id"])


@router.post("/strategies", response_model=QuantSavedStrategy)
async def save_quant_strategy(
    request: QuantStrategySave,
    user: AuthenticatedUser = Depends(require_active_user),
):
    return await save_user_strategy(request, user["id"])


@router.delete("/strategies/{strategy_id}", response_model=QuantDeleteResponse)
async def delete_quant_strategy(strategy_id: int, user: AuthenticatedUser = Depends(require_active_user)):
    if not await delete_user_strategy(strategy_id, user["id"]):
        raise NotFoundError("策略不存在", code="quant.strategy_not_found")
    return QuantDeleteResponse(deleted=True)


@router.post("/backtests", response_model=QuantBacktestRun, status_code=status.HTTP_202_ACCEPTED)
async def create_quant_backtest(
    request: QuantBacktestCreate,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await create_backtest(request, user["id"])
    except RuntimeError as error:
        raise ConflictError(str(error), code="quant.active_limit") from error
    except ValueError as error:
        raise BadRequestError(str(error), code="quant.invalid_request") from error


@router.get("/backtests", response_model=QuantBacktestList)
async def get_quant_backtests(
    limit: int = Query(default=50, ge=1, le=100),
    user: AuthenticatedUser = Depends(require_active_user),
):
    return await list_backtests(user["id"], limit=limit)


@router.get("/backtests/{run_id}", response_model=QuantBacktestRun)
async def get_quant_backtest(run_id: str, user: AuthenticatedUser = Depends(require_active_user)):
    run = await get_backtest(run_id, user["id"])
    if run is None:
        raise NotFoundError("回测记录不存在", code="quant.run_not_found")
    return run


@router.post("/backtests/{run_id}/cancel", response_model=QuantBacktestRun)
async def cancel_quant_backtest(run_id: str, user: AuthenticatedUser = Depends(require_active_user)):
    run = await get_backtest(run_id, user["id"])
    if run is None:
        raise NotFoundError("回测记录不存在", code="quant.run_not_found")
    if not await cancel_backtest(run_id, user["id"]):
        raise ConflictError("仅等待中或运行中的回测可以取消", code="quant.run_not_cancellable")
    return await get_backtest(run_id, user["id"])


@router.post("/backtests/{run_id}/retry", response_model=QuantBacktestRun)
async def retry_quant_backtest(run_id: str, user: AuthenticatedUser = Depends(require_active_user)):
    run = await get_backtest(run_id, user["id"])
    if run is None:
        raise NotFoundError("回测记录不存在", code="quant.run_not_found")
    if not await retry_backtest(run_id, user["id"]):
        raise ConflictError("仅失败的回测可以重试", code="quant.run_not_retryable")
    return await get_backtest(run_id, user["id"])


@router.delete("/backtests/{run_id}", response_model=QuantDeleteResponse)
async def delete_quant_backtest(run_id: str, user: AuthenticatedUser = Depends(require_active_user)):
    run = await get_backtest(run_id, user["id"])
    if run is None:
        raise NotFoundError("回测记录不存在", code="quant.run_not_found")
    if not await delete_backtest(run_id, user["id"]):
        raise ConflictError("运行中的回测不能删除", code="quant.run_not_deletable")
    return QuantDeleteResponse(deleted=True)
