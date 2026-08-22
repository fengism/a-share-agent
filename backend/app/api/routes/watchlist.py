from fastapi import APIRouter, Depends, status

from app.api.auth.dependencies import require_active_user
from app.api.errors import BadRequestError, NotFoundError
from app.api.schemas import DeleteResponse
from app.domain.identity import AuthenticatedUser
from app.modules.watchlist.public import (
    UnknownWatchlistStockError,
    WatchlistAlert,
    WatchlistAlertCreate,
    WatchlistItem,
    WatchlistItemCreate,
    WatchlistItemNotFoundError,
    WatchlistResponse,
    add_watchlist_alert,
    add_watchlist_item,
    get_watchlist,
    remove_watchlist_alert,
    remove_watchlist_item,
)

router = APIRouter()


@router.get("", response_model=WatchlistResponse)
async def list_watchlist(user: AuthenticatedUser = Depends(require_active_user)):
    return await get_watchlist(user["id"])


@router.post("", response_model=WatchlistItem, status_code=status.HTTP_201_CREATED)
async def create_watchlist_item(
    request: WatchlistItemCreate,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await add_watchlist_item(request, user["id"])
    except UnknownWatchlistStockError as error:
        raise BadRequestError("无法识别该股票代码", code="watchlist.unknown_stock") from error


@router.delete("/{stock_code}", response_model=DeleteResponse)
async def delete_watchlist_item(
    stock_code: str,
    user: AuthenticatedUser = Depends(require_active_user),
):
    if not await remove_watchlist_item(stock_code, user["id"]):
        raise NotFoundError("自选股不存在", code="watchlist.item_not_found")
    return DeleteResponse()


@router.post("/{stock_code}/alerts", response_model=WatchlistAlert, status_code=status.HTTP_201_CREATED)
async def create_watchlist_alert(
    stock_code: str,
    request: WatchlistAlertCreate,
    user: AuthenticatedUser = Depends(require_active_user),
):
    try:
        return await add_watchlist_alert(stock_code, request, user["id"])
    except WatchlistItemNotFoundError as error:
        raise NotFoundError("请先添加自选股", code="watchlist.item_not_found") from error


@router.delete("/alerts/{alert_id}", response_model=DeleteResponse)
async def delete_watchlist_alert(
    alert_id: int,
    user: AuthenticatedUser = Depends(require_active_user),
):
    if not await remove_watchlist_alert(alert_id, user["id"]):
        raise NotFoundError("提醒规则不存在", code="watchlist.alert_not_found")
    return DeleteResponse()
