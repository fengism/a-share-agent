"""个股 API 聚合路由。"""

from fastapi import APIRouter

from app.api.routes.stock_sections import fundamentals, insights, profile, quotes

router = APIRouter()
router.include_router(profile.router)
router.include_router(quotes.router)
router.include_router(fundamentals.router)
router.include_router(insights.router)

__all__ = ["router"]
