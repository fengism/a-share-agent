from fastapi import APIRouter, Depends

from app.api.errors import BadRequestError, NotFoundError
from app.modules.auth.public import AuthenticatedUser, require_active_user
from app.modules.portfolio.schemas import (
    PortfolioDeleteResponse,
    PortfolioPosition,
    PortfolioPositionCreate,
    PortfolioResponse,
)
from app.modules.portfolio.service import add_position as add_position_service
from app.modules.portfolio.service import delete_position as delete_position_service
from app.modules.portfolio.service import (
    get_portfolio as get_portfolio_service,
)

router = APIRouter()


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(user: AuthenticatedUser = Depends(require_active_user)):
    return await get_portfolio_service(user["id"])


@router.post("", response_model=PortfolioPosition)
async def add_position(request: PortfolioPositionCreate, user: AuthenticatedUser = Depends(require_active_user)):
    position = await add_position_service(request, user["id"])
    if position is None:
        raise BadRequestError("无法识别该股票代码", code="portfolio.unknown_stock")
    return position


@router.delete("/{position_id}", response_model=PortfolioDeleteResponse)
async def delete_position(position_id: int, user: AuthenticatedUser = Depends(require_active_user)):
    deleted = await delete_position_service(position_id, user["id"])
    if not deleted:
        raise NotFoundError("持仓记录不存在", code="portfolio.position_not_found")
    return PortfolioDeleteResponse(deleted=True)
