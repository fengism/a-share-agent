"""分析页面聚合 HTTP 端点。"""

from fastapi import APIRouter, Depends

from app.api.auth.dependencies import require_active_user
from app.configuration import get_effective_settings
from app.domain.identity import AuthenticatedUser
from app.modules.analysis.public import AnalysisPageData, get_analysis_page_data

router = APIRouter()


@router.get("/analysis-page/{code}", response_model=AnalysisPageData)
async def get_analysis_page(code: str, user: AuthenticatedUser = Depends(require_active_user)):
    """聚合分析页面所需的所有数据，并发加载。

    将 stock/info、stock/kline、stock/intraday、stock/valuation、analysis/result
    合并为一个响应，减少前端页面加载时的 HTTP 往返次数。

    Param:
        code: 6 位股票代码
    Return:
        AnalysisPageData: 分析页面所需的全部数据
    """
    settings = get_effective_settings()
    return await get_analysis_page_data(
        code,
        user_id=user["id"],
        cache_ttl=settings.cache_ttl_analysis,
        section_timeout_seconds=settings.analysis_page_section_timeout_seconds,
    )
