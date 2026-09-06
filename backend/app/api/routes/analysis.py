"""AI 分析历史与执行 HTTP 路由聚合入口。"""

import asyncio
import logging
from datetime import date as calendar_date
from datetime import datetime, timedelta
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response

from app.api.auth.dependencies import require_active_user
from app.api.errors import NotFoundError
from app.api.routes import analysis_execution
from app.api.schemas import DeleteResponse
from app.domain.identity import AuthenticatedUser
from app.domain.market import KlineData
from app.financial_data.stock.profile.basic_info import get_basic_info
from app.financial_data.stock.quotes.chip_distribution import calculate_chip_distribution
from app.financial_data.stock.quotes.chip_schemas import ChipDistribution
from app.financial_data.stock.quotes.kline import get_kline
from app.modules.analysis.public import (
    AnalysisHistoryItem,
    AnalysisResult,
    generate_research_report_html,
    list_all_analysis_history,
    list_analysis_history,
    load_analysis_history,
    load_latest_analysis,
    remove_analysis_history,
    render_pdf_bytes_from_html,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _pdf_market_end_date(analysis_date: str) -> calendar_date:
    """将报告日期转换为行情截止日，避免历史报告引用未来数据。"""
    for date_format in ("%Y-%m-%d", "%Y%m%d"):
        try:
            parsed = datetime.strptime(analysis_date, date_format).date()
            return min(parsed, calendar_date.today())
        except (TypeError, ValueError):
            continue
    return calendar_date.today()


async def _load_pdf_visual_data(
    code: str,
    analysis_date: str,
) -> tuple[KlineData | None, ChipDistribution | None]:
    """尽力加载 PDF 图表数据；行情或筹码失败时不影响文字报告导出。"""
    end_date = _pdf_market_end_date(analysis_date)
    start_date = end_date - timedelta(days=400)
    try:
        kline_data = await asyncio.wait_for(
            get_kline(
                code,
                period="daily",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                adjust="qfq",
            ),
            timeout=15,
        )
    except Exception as exc:
        logger.warning("PDF 行情图数据加载失败 code=%s: %s", code, exc)
        return None, None

    try:
        chip_distribution = calculate_chip_distribution(kline_data.items, code=kline_data.code)
    except Exception as exc:
        logger.warning("PDF 筹码图数据计算失败 code=%s: %s", code, exc)
        chip_distribution = None
    return kline_data, chip_distribution


@router.get("/history/all", response_model=list[AnalysisHistoryItem])
async def get_all_analysis_history(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """获取所有股票的历史 AI 分析记录列表。

    Return:
        list[AnalysisHistoryItem]: 全部历史分析条目集合。
    """
    return await list_all_analysis_history(
        user["id"],
        limit=limit,
        offset=offset,
        can_delete_legacy=bool(user["is_admin"]),
        query=q,
    )


@router.post("/export-pdf")
async def export_custom_analysis_pdf(
    result: AnalysisResult,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """基于前端传入的实时分析结果对象直接生成纯矢量投研 PDF。"""
    code = getattr(result, "stock_code", None) or getattr(result, "code", "stock")
    stock_info_dict = None
    try:
        basic_info = await get_basic_info(code)
        if basic_info:
            stock_info_dict = basic_info.model_dump()
    except Exception:
        pass

    kline_data, chip_distribution = await _load_pdf_visual_data(
        code,
        getattr(result, "analysis_date", ""),
    )
    html_content = generate_research_report_html(
        result,
        stock_info=stock_info_dict,
        kline_data=kline_data,
        chip_distribution=chip_distribution,
    )
    pdf_bytes = await render_pdf_bytes_from_html(html_content)

    stock_name = getattr(result, "stock_name", None) or getattr(result, "name", "") or code
    report_date = getattr(result, "analysis_date", "") or "最新"
    filename = f"{code}_{stock_name}_深度投研报告_{report_date}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/{code}/export-pdf")
async def export_analysis_pdf(
    code: str,
    date: Annotated[str | None, Query()] = None,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """根据股票代码与日期，通过无头浏览器直接生成纯矢量投研 PDF 并下载。"""
    if date:
        result = await load_analysis_history(code, date, user["id"])
    else:
        result = await load_latest_analysis(code, user["id"])

    if result is None:
        raise NotFoundError(
            f"未找到 {code} 的分析记录，请先执行研究后再导出",
            code="analysis.not_found",
        )

    stock_info_dict = None
    try:
        basic_info = await get_basic_info(code)
        if basic_info:
            stock_info_dict = basic_info.model_dump()
    except Exception:
        pass

    kline_data, chip_distribution = await _load_pdf_visual_data(
        code,
        getattr(result, "analysis_date", ""),
    )
    html_content = generate_research_report_html(
        result,
        stock_info=stock_info_dict,
        kline_data=kline_data,
        chip_distribution=chip_distribution,
    )
    pdf_bytes = await render_pdf_bytes_from_html(html_content)

    stock_name = getattr(result, "stock_name", None) or getattr(result, "name", "") or code
    report_date = getattr(result, "analysis_date", "") or "最新"
    filename = f"{code}_{stock_name}_深度投研报告_{report_date}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/{code}/history", response_model=list[AnalysisHistoryItem])
async def get_analysis_history(
    code: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: AuthenticatedUser = Depends(require_active_user),
):
    """读取指定股票的历史分析索引列表。

    Param:
        code: 股票代码（路径参数），6 位数字。
    Return:
        list[AnalysisHistoryItem]: 按日期排序的历史分析摘要条目。
    """
    return await list_analysis_history(
        code,
        user["id"],
        limit=limit,
        offset=offset,
        can_delete_legacy=bool(user["is_admin"]),
    )


@router.get("/{code}/history/{date}", response_model=AnalysisResult)
async def get_analysis_by_date(code: str, date: str, user: AuthenticatedUser = Depends(require_active_user)):
    """读取指定股票在指定日期的分析结果，命中缓存优先。

    Param:
        code: 股票代码（路径参数），6 位数字。
        date: 分析日期（路径参数），格式 YYYYMMDD。
    Return:
        AnalysisResult: 该日的完整分析结果；若不存在则返回 404。
    """
    result = await load_analysis_history(code, date, user["id"])
    if result is None:
        raise NotFoundError(
            f"未找到 {code} 在 {date} 的分析记录",
            code="analysis.history_not_found",
        )
    return result


@router.delete("/{code}/history/{date}", response_model=DeleteResponse)
async def delete_analysis_history(
    code: str,
    date: str,
    user: AuthenticatedUser = Depends(require_active_user),
) -> DeleteResponse:
    deleted = await remove_analysis_history(
        code,
        date,
        user["id"],
        can_delete_legacy=bool(user["is_admin"]),
    )
    if not deleted:
        raise NotFoundError("分析记录不存在", code="analysis.history_not_found")
    return DeleteResponse()


# 注意：analysis_execution 包含动态通配路由 POST /{code}，必须放在静态路由之后加载！
router.include_router(analysis_execution.router)
