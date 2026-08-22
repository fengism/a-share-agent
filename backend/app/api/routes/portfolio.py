"""投资组合 HTTP API。"""

from fastapi import APIRouter, Depends

from app.api.auth.dependencies import require_active_user
from app.api.errors import BadRequestError, NotFoundError
from app.api.schemas import DeleteResponse
from app.domain.identity import AuthenticatedUser
from app.modules.portfolio.public import (
    InsufficientSharesError,
    PortfolioPosition,
    PortfolioPositionCreate,
    PortfolioResponse,
    PortfolioTransaction,
    PortfolioTransactionCreate,
    PortfolioTransactionNotFoundError,
    PortfolioTransactionPreview,
    UnknownPortfolioStockError,
)
from app.modules.portfolio.public import add_position as add_position_service
from app.modules.portfolio.public import create_transaction as create_transaction_service
from app.modules.portfolio.public import delete_position as delete_position_service
from app.modules.portfolio.public import delete_transaction as delete_transaction_service
from app.modules.portfolio.public import get_portfolio as get_portfolio_service
from app.modules.portfolio.public import preview_transaction as preview_transaction_service
from app.modules.portfolio.public import preview_transaction_update as preview_transaction_update_service
from app.modules.portfolio.public import update_transaction as update_transaction_service

router = APIRouter()


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(user: AuthenticatedUser = Depends(require_active_user)):
    return await get_portfolio_service(user["id"])


@router.post("", response_model=PortfolioPosition)
async def add_position(request: PortfolioPositionCreate, user: AuthenticatedUser = Depends(require_active_user)):
    try:
        position = await add_position_service(request, user["id"])
    except InsufficientSharesError as error:
        raise BadRequestError(
            "新增记录会导致历史持仓无效",
            code="portfolio.invalid_history",
        ) from error
    if position is None:
        raise BadRequestError("无法识别该股票代码", code="portfolio.unknown_stock")
    return position


@router.post("/transactions", response_model=PortfolioTransaction)
async def create_transaction(
    request: PortfolioTransactionCreate,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        transaction = await create_transaction_service(request, user["id"])
    except InsufficientSharesError as error:
        raise BadRequestError(
            f"卖出股数超过交易时点可用持仓（可用 {error.available_shares} 股）",
            code="portfolio.insufficient_shares",
        ) from error
    if transaction is None:
        raise BadRequestError("无法识别该股票代码", code="portfolio.unknown_stock")
    return transaction


@router.post("/transactions/preview", response_model=PortfolioTransactionPreview)
async def preview_transaction(
    request: PortfolioTransactionCreate,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        preview = await preview_transaction_service(request, user["id"])
    except InsufficientSharesError as error:
        raise BadRequestError(
            f"卖出股数超过交易时点可用持仓（可用 {error.available_shares} 股）",
            code="portfolio.insufficient_shares",
        ) from error
    if preview is None:
        raise BadRequestError("无法识别该股票代码", code="portfolio.unknown_stock")
    return preview


@router.post("/transactions/{transaction_id}/preview", response_model=PortfolioTransactionPreview)
async def preview_transaction_update(
    transaction_id: int,
    request: PortfolioTransactionCreate,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await preview_transaction_update_service(transaction_id, request, user["id"])
    except InsufficientSharesError as error:
        raise BadRequestError(
            f"修改后会导致历史卖出超出持仓（可用 {error.available_shares} 股）",
            code="portfolio.invalid_history",
        ) from error
    except UnknownPortfolioStockError as error:
        raise BadRequestError("无法识别该股票代码", code="portfolio.unknown_stock") from error
    except PortfolioTransactionNotFoundError as error:
        raise NotFoundError("交易流水不存在", code="portfolio.transaction_not_found") from error


@router.put("/transactions/{transaction_id}", response_model=PortfolioTransaction)
async def update_transaction(
    transaction_id: int,
    request: PortfolioTransactionCreate,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await update_transaction_service(transaction_id, request, user["id"])
    except InsufficientSharesError as error:
        raise BadRequestError(
            f"修改后会导致历史卖出超出持仓（可用 {error.available_shares} 股）",
            code="portfolio.invalid_history",
        ) from error
    except UnknownPortfolioStockError as error:
        raise BadRequestError("无法识别该股票代码", code="portfolio.unknown_stock") from error
    except PortfolioTransactionNotFoundError as error:
        raise NotFoundError("交易流水不存在", code="portfolio.transaction_not_found") from error


@router.delete("/transactions/{transaction_id}", response_model=DeleteResponse)
async def delete_transaction(
    transaction_id: int,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        deleted = await delete_transaction_service(transaction_id, user["id"])
    except InsufficientSharesError as error:
        raise BadRequestError(
            "删除后会导致历史时点卖出超出持仓，无法删除",
            code="portfolio.invalid_history",
        ) from error
    if not deleted:
        raise NotFoundError("交易流水不存在", code="portfolio.transaction_not_found")
    return DeleteResponse()


@router.delete("/{position_id}", response_model=DeleteResponse)
async def delete_position(position_id: int, user: AuthenticatedUser = Depends(require_active_user)):
    try:
        deleted = await delete_position_service(position_id, user["id"])
    except InsufficientSharesError as error:
        raise BadRequestError(
            "删除后会导致历史时点卖出超出持仓，无法删除",
            code="portfolio.invalid_history",
        ) from error
    if not deleted:
        raise NotFoundError("持仓记录不存在", code="portfolio.position_not_found")
    return DeleteResponse()
