"""量化研究 HTTP API。"""

from fastapi import APIRouter, Depends, Query, status

from app.api.auth.dependencies import require_active_user, require_admin
from app.api.errors import ApiError, BadRequestError, ConflictError, NotFoundError
from app.api.rate_limit import llm_rate_limit
from app.api.schemas import DeleteResponse
from app.domain.identity import AuthenticatedUser
from app.modules.quant.public import (
    QuantBacktestCreate,
    QuantBacktestList,
    QuantBacktestRun,
    QuantParameterScanRequest,
    QuantParameterScanResult,
    QuantSavedStrategy,
    QuantStrategyDraft,
    QuantStrategyDraftBacktestRequest,
    QuantStrategyDraftGenerateRequest,
    QuantStrategyDraftPublishRequest,
    QuantStrategyDraftUpdateRequest,
    QuantStrategyPreset,
    QuantStrategyRegistryStatus,
    QuantStrategySave,
    StrategyDraftConflictError,
    StrategyDraftGenerationError,
    StrategyDraftNotFoundError,
    backtest_strategy_draft,
    cancel_backtest,
    create_backtest,
    delete_backtest,
    delete_strategy_draft,
    delete_user_strategy,
    generate_strategy_draft,
    get_backtest,
    get_strategy_draft,
    list_backtests,
    list_strategy_drafts,
    list_user_strategies,
    publish_strategy_draft,
    retry_backtest,
    save_user_strategy,
    scan_parameter_sensitivity,
    strategy_presets,
    strategy_registry_status,
    update_strategy_draft,
    validate_strategy_draft,
)

router = APIRouter()


def _owner_scope(user: AuthenticatedUser) -> int | None:
    """草稿归属过滤：管理员（``is_admin``）看全量，普通用户只看自己创建的。"""
    return None if bool(user.get("is_admin")) else int(user["id"])


@router.get("/strategy-presets", response_model=list[QuantStrategyPreset])
async def get_strategy_presets():
    return strategy_presets()


@router.get("/strategy-registry", response_model=QuantStrategyRegistryStatus)
async def get_strategy_registry_status(
    _user: AuthenticatedUser = Depends(require_admin),
):
    return strategy_registry_status()


@router.get("/strategy-drafts", response_model=list[QuantStrategyDraft])
async def get_strategy_drafts(
    limit: int = Query(default=100, ge=1, le=200),
    user: AuthenticatedUser = Depends(require_active_user),
):
    """列出策略草稿：普通用户只返回自己创建的，管理员返回全量。"""
    return await list_strategy_drafts(limit=limit, owner_id=_owner_scope(user))


@router.post(
    "/strategy-drafts/generate",
    response_model=QuantStrategyDraft,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(llm_rate_limit)],
)
async def generate_quant_strategy_draft(
    request: QuantStrategyDraftGenerateRequest,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await generate_strategy_draft(request, user_id=user["id"])
    except StrategyDraftGenerationError as error:
        raise ApiError(
            status_code=502,
            code="quant.strategy_generation_failed",
            message=str(error),
        ) from error
    except ValueError as error:
        raise BadRequestError(str(error), code="quant.invalid_strategy_definition") from error


@router.get("/strategy-drafts/{draft_id}", response_model=QuantStrategyDraft)
async def get_quant_strategy_draft(
    draft_id: str,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await get_strategy_draft(draft_id, owner_id=_owner_scope(user))
    except StrategyDraftNotFoundError as error:
        raise NotFoundError(str(error), code="quant.strategy_draft_not_found") from error


@router.put("/strategy-drafts/{draft_id}", response_model=QuantStrategyDraft)
async def update_quant_strategy_draft(
    draft_id: str,
    request: QuantStrategyDraftUpdateRequest,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await update_strategy_draft(
            draft_id, request, owner_id=_owner_scope(user)
        )
    except StrategyDraftNotFoundError as error:
        raise NotFoundError(str(error), code="quant.strategy_draft_not_found") from error
    except StrategyDraftConflictError as error:
        raise ConflictError(str(error), code="quant.strategy_draft_conflict") from error


@router.post("/strategy-drafts/{draft_id}/validate", response_model=QuantStrategyDraft)
async def validate_quant_strategy_draft(
    draft_id: str,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await validate_strategy_draft(draft_id, owner_id=_owner_scope(user))
    except StrategyDraftNotFoundError as error:
        raise NotFoundError(str(error), code="quant.strategy_draft_not_found") from error
    except StrategyDraftConflictError as error:
        raise ConflictError(str(error), code="quant.strategy_draft_conflict") from error
    except ValueError as error:
        raise BadRequestError(str(error), code="quant.invalid_strategy_definition") from error


@router.post(
    "/strategy-drafts/{draft_id}/backtest",
    response_model=QuantBacktestRun,
    status_code=status.HTTP_202_ACCEPTED,
)
async def backtest_quant_strategy_draft(
    draft_id: str,
    request: QuantStrategyDraftBacktestRequest,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await backtest_strategy_draft(
            draft_id,
            request,
            user_id=user["id"],
            owner_id=_owner_scope(user),
        )
    except StrategyDraftNotFoundError as error:
        raise NotFoundError(str(error), code="quant.strategy_draft_not_found") from error
    except StrategyDraftConflictError as error:
        raise ConflictError(str(error), code="quant.strategy_draft_conflict") from error
    except RuntimeError as error:
        raise ConflictError(str(error), code="quant.active_limit") from error
    except ValueError as error:
        raise BadRequestError(str(error), code="quant.invalid_request") from error


@router.post("/strategy-drafts/{draft_id}/publish", response_model=QuantStrategyDraft)
async def publish_quant_strategy_draft(
    draft_id: str,
    request: QuantStrategyDraftPublishRequest,
    _user: AuthenticatedUser = Depends(require_admin),
):
    try:
        return await publish_strategy_draft(
            draft_id,
            expected_definition_hash=request.expected_definition_hash,
        )
    except StrategyDraftNotFoundError as error:
        raise NotFoundError(str(error), code="quant.strategy_draft_not_found") from error
    except StrategyDraftConflictError as error:
        raise ConflictError(str(error), code="quant.strategy_draft_conflict") from error
    except ValueError as error:
        raise BadRequestError(str(error), code="quant.invalid_strategy_definition") from error


@router.delete("/strategy-drafts/{draft_id}", response_model=DeleteResponse)
async def delete_quant_strategy_draft(
    draft_id: str,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        if not await delete_strategy_draft(draft_id, owner_id=_owner_scope(user)):
            raise StrategyDraftNotFoundError("策略草稿不存在")
    except StrategyDraftNotFoundError as error:
        raise NotFoundError(str(error), code="quant.strategy_draft_not_found") from error
    except StrategyDraftConflictError as error:
        raise ConflictError(str(error), code="quant.strategy_draft_conflict") from error
    return DeleteResponse()


@router.get("/strategies", response_model=list[QuantSavedStrategy])
async def get_saved_strategies(user: AuthenticatedUser = Depends(require_active_user)):
    return await list_user_strategies(user["id"])


@router.post("/strategies", response_model=QuantSavedStrategy)
async def save_quant_strategy(
    request: QuantStrategySave,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await save_user_strategy(request, user["id"])
    except ValueError as error:
        raise BadRequestError(str(error), code="quant.invalid_strategy") from error


@router.delete("/strategies/{strategy_id}", response_model=DeleteResponse)
async def delete_quant_strategy(strategy_id: int, user: AuthenticatedUser = Depends(require_active_user)):
    if not await delete_user_strategy(strategy_id, user["id"]):
        raise NotFoundError("策略不存在", code="quant.strategy_not_found")
    return DeleteResponse()


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
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(require_active_user),
):
    return await list_backtests(user["id"], limit=limit, offset=offset)


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


@router.delete("/backtests/{run_id}", response_model=DeleteResponse)
async def delete_quant_backtest(run_id: str, user: AuthenticatedUser = Depends(require_active_user)):
    run = await get_backtest(run_id, user["id"])
    if run is None:
        raise NotFoundError("回测记录不存在", code="quant.run_not_found")
    if not await delete_backtest(run_id, user["id"]):
        raise ConflictError("运行中的回测不能删除", code="quant.run_not_deletable")
    return DeleteResponse()


@router.post("/backtests/{run_id}/sensitivity-scan", response_model=QuantParameterScanResult)
async def scan_backtest_parameter_sensitivity(
    run_id: str,
    request: QuantParameterScanRequest,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await scan_parameter_sensitivity(run_id, request, user["id"])
    except ValueError as error:
        raise BadRequestError(str(error), code="quant.invalid_scan_request") from error

