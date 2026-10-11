"""市场行情与资金流 HTTP API。"""

from datetime import date as Date

from fastapi import APIRouter, Depends, Query

from app.api.auth.dependencies import require_admin
from app.core.market import normalize_code
from app.domain.identity import AuthenticatedUser
from app.domain.market import KlineData, MarketIndices
from app.financial_data.market.public import (
    DragonTigerItem,
    HsgtFlowHistoryItem,
    HsgtFlowResponse,
    IndexIntradayData,
    IndustryRankings,
    MarketBreadthResponse,
    MarketEmotion,
    MarketLimitHistoryCategory,
    MarketLimitHistoryResponse,
    MarketLimitUpLadderResponse,
    MarketMainlineResponse,
    MarketMarginResponse,
    MarketPriceAnomalyCountResponse,
    MarketPriceAnomalyResponse,
    MarketSectorStocksHistoryResponse,
    MarketVolumeResponse,
    MarketWindResponse,
    MarketWindStocksResponse,
    NationalTeamResponse,
    NorthboundHistoryResponse,
    ThsHotPlate,
    ThsHotStock,
    TradingCalendarResponse,
)
from app.financial_data.market.public import get_dragon_tiger_list as get_dragon_tiger_list_service
from app.financial_data.market.public import get_hot_stocks as get_hot_stocks_service
from app.financial_data.market.public import get_hsgt_flow as get_hsgt_flow_service
from app.financial_data.market.public import get_hsgt_flow_history as get_hsgt_flow_history_service
from app.financial_data.market.public import get_index_intraday as get_index_intraday_service
from app.financial_data.market.public import get_index_kline as get_index_kline_service
from app.financial_data.market.public import get_indices as get_indices_service
from app.financial_data.market.public import get_industry_rankings as get_industry_rankings_service
from app.financial_data.market.public import get_limit_history as get_limit_history_service
from app.financial_data.market.public import get_limit_up_ladder as get_limit_up_ladder_service
from app.financial_data.market.public import get_market_breadth as get_market_breadth_service
from app.financial_data.market.public import get_market_emotion as get_market_emotion_service
from app.financial_data.market.public import get_market_mainline as get_market_mainline_service
from app.financial_data.market.public import get_market_margin as get_market_margin_service
from app.financial_data.market.public import (
    get_market_price_anomaly as get_market_price_anomaly_service,
)
from app.financial_data.market.public import (
    get_market_price_anomaly_count as get_market_price_anomaly_count_service,
)
from app.financial_data.market.public import get_market_volume as get_market_volume_service
from app.financial_data.market.public import get_market_wind as get_market_wind_service
from app.financial_data.market.public import get_market_wind_stocks as get_market_wind_stocks_service
from app.financial_data.market.public import (
    get_national_team_etf_holdings as get_national_team_etf_holdings_service,
)
from app.financial_data.market.public import get_northbound_history as get_northbound_history_service
from app.financial_data.market.public import get_sector_stocks_history as get_sector_stocks_history_service
from app.financial_data.market.public import get_ths_hot_concept as get_ths_hot_concept_service
from app.financial_data.market.public import get_ths_hot_industry as get_ths_hot_industry_service
from app.financial_data.market.public import get_trading_calendar_view as get_trading_calendar_view_service
from app.modules.market_daily.adjustment import (
    get_adjustment_factor_status,
    invalidate_adjustment_factors,
    refresh_adjustment_factors,
)
from app.modules.market_daily.backfill import market_daily_backfill_service
from app.modules.market_daily.models import (
    MarketAdjustmentFactorInvalidateRequest,
    MarketAdjustmentFactorRefreshRequest,
    MarketAdjustmentFactorStatus,
    MarketDailyBackfillJob,
    MarketDailyBackfillJobList,
    MarketDailyBackfillRequest,
    MarketDailyBarDeleteRequest,
    MarketDailyBarDeleteResult,
    MarketDailyBarPage,
    MarketDailyBarRefreshHistory,
    MarketDailyBarRefreshRequest,
    MarketDailyBarRefreshResult,
    MarketDailyBarRefreshStatus,
)
from app.modules.market_daily.service import market_daily_bar_service

router = APIRouter()


@router.get("/emotion", response_model=MarketEmotion)
async def get_market_emotion():
    """获取财联社实时市场情绪。"""
    return await get_market_emotion_service()


@router.get("/mainline", response_model=MarketMainlineResponse)
async def get_market_mainline():
    """获取财联社今日主线机会。"""
    return await get_market_mainline_service()


@router.get("/limit-up-ladder", response_model=MarketLimitUpLadderResponse)
async def get_limit_up_ladder(
    date: Date | None = Query(None, description="查询日期 YYYY-MM-DD，默认当天"),
):
    """获取开盘红涨停天梯与板块涨停分布。"""
    return await get_limit_up_ladder_service(date)


@router.get("/limit-history", response_model=MarketLimitHistoryResponse)
async def get_limit_history(
    date: Date = Query(..., description="历史日期 YYYY-MM-DD，必须早于今天"),
    category: MarketLimitHistoryCategory = Query(
        ...,
        description="limit_up / limit_down / wind_vane",
    ),
):
    """获取开盘红历史涨停、跌停或风向标列表。"""
    return await get_limit_history_service(date, category)


@router.get("/sector-stocks-history", response_model=MarketSectorStocksHistoryResponse)
async def get_sector_stocks_history(
    date: Date = Query(..., description="查询日期 YYYY-MM-DD，支持当天和历史日期"),
    plate_id: str = Query(..., min_length=1, description="开盘红板块 ID，例如 881169"),
):
    """获取开盘红板块成分股；当天补充股票实时行情。"""
    return await get_sector_stocks_history_service(date, plate_id)


@router.get("/trading-calendar", response_model=TradingCalendarResponse)
async def get_trading_calendar(
    start_date: Date | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Date | None = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """获取 A 股交易日历（区间列表与今日交易状态）。"""
    return await get_trading_calendar_view_service(start_date, end_date)


@router.get("/margin", response_model=MarketMarginResponse)
async def get_market_margin(
    days: int = Query(240, description="返回的交易日数量，30-500"),
):
    """获取沪深两市融资融券历史合计（日级，单位亿元）。"""
    return await get_market_margin_service(days)


@router.get("/breadth", response_model=MarketBreadthResponse)
async def get_market_breadth(
    days: int = Query(60, ge=10, le=120, description="返回的交易日数量，10-120"),
):
    """获取申万2级行业市场宽度热力图（收盘价站上 MA20 股票占比）。"""
    return await get_market_breadth_service(days)


@router.get(
    "/national-team-etf-holdings",
    response_model=NationalTeamResponse,
)
async def get_national_team_etf_holdings(
    days: int = Query(120, ge=30, le=365, description="返回最近自然日数量，30-365"),
):
    """获取核心宽基 ETF 份额变化与国家队持仓代理监测。"""
    return await get_national_team_etf_holdings_service(days)


@router.get("/price-anomaly", response_model=MarketPriceAnomalyResponse)
async def get_market_price_anomaly(
    page_size: int = Query(200, ge=1, le=200, description="每页条数"),
    page_no: int = Query(1, ge=1, description="页码"),
):
    """获取交易所异动明细。"""
    return await get_market_price_anomaly_service(page_size, page_no)


@router.get("/price-anomaly/count", response_model=MarketPriceAnomalyCountResponse)
async def get_market_price_anomaly_count(
    page_size: int = Query(50, ge=1, le=200, description="每页条数"),
    page_no: int = Query(1, ge=1, description="页码"),
    sort_key: str = Query("", max_length=32, description="排序字段"),
    sort_dir: str = Query("", pattern=r"^(|asc|desc)$", description="排序方向"),
):
    """获取按标的聚合的交易所异动统计。"""
    return await get_market_price_anomaly_count_service(
        page_size,
        page_no,
        sort_key,
        sort_dir,
    )


@router.get("/today-wind", response_model=MarketWindResponse)
async def get_market_wind():
    """获取财联社今日风口板块。"""
    return await get_market_wind_service()


@router.get("/today-wind/{plate_code}/stocks", response_model=MarketWindStocksResponse)
async def get_market_wind_stocks(plate_code: str):
    """获取指定风口板块的龙头股。"""
    return await get_market_wind_stocks_service(plate_code)


@router.post("/daily-bars/backfill", response_model=MarketDailyBackfillJob)
async def create_market_daily_backfill(
    request: MarketDailyBackfillRequest,
    _user: AuthenticatedUser = Depends(require_admin),
):
    """创建 A 股全市场历史日线后台回填任务。"""
    return await market_daily_backfill_service.create(request)


@router.get("/daily-bars/backfill", response_model=MarketDailyBackfillJobList)
async def list_market_daily_backfills(
    limit: int = Query(20, ge=1, le=100),
    _user: AuthenticatedUser = Depends(require_admin),
):
    """查看历史日线回填任务与进度。"""
    return await market_daily_backfill_service.list_jobs(limit=limit)


@router.get("/daily-bars/backfill/{job_id}", response_model=MarketDailyBackfillJob)
async def get_market_daily_backfill(
    job_id: str,
    _user: AuthenticatedUser = Depends(require_admin),
):
    return await market_daily_backfill_service.get(job_id)


@router.post("/daily-bars/backfill/{job_id}/retry-failed", response_model=MarketDailyBackfillJob)
async def retry_failed_market_daily_backfill(
    job_id: str,
    _user: AuthenticatedUser = Depends(require_admin),
):
    """仅重试历史回填任务中的失败股票。"""
    return await market_daily_backfill_service.retry_failed(job_id)


@router.post("/daily-bars/backfill/{job_id}/cancel", response_model=MarketDailyBackfillJob)
async def cancel_market_daily_backfill(
    job_id: str,
    _user: AuthenticatedUser = Depends(require_admin),
):
    return await market_daily_backfill_service.cancel(job_id)


@router.get("/daily-bars", response_model=MarketDailyBarPage)
async def get_market_daily_bars(
    market: str | None = Query(None, pattern=r"^(cn|hk)$"),
    instrument_type: str | None = Query(None, pattern=r"^(stock|index)$"),
    trade_date: Date | None = Query(None, description="单日查询；不能与日期范围同时使用"),
    start_date: Date | None = Query(None, description="范围起始日期，需与 end_date 同时提供"),
    end_date: Date | None = Query(None, description="范围结束日期，需与 start_date 同时提供"),
    codes: str = Query("", description="逗号分隔的证券代码；不传任何日期时读取最近可用交易日"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    cursor: str | None = Query(None, description="深分页游标；使用时 page 必须为 1"),
):
    """按单日或日期范围读取独立 SQLite 中的 A/H 股及指数日行情。"""
    code_list = [item.strip() for item in codes.split(",") if item.strip()]
    return await market_daily_bar_service.query(
        market=market,
        instrument_type=instrument_type,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
        codes=code_list or None,
        page=page,
        page_size=page_size,
        cursor=cursor,
    )


@router.get("/daily-bars/status", response_model=list[MarketDailyBarRefreshStatus])
async def get_market_daily_bar_refresh_status(
    trade_date: Date = Query(...),
    _user: AuthenticatedUser = Depends(require_admin),
):
    """管理员查看指定日期刷新状态。"""
    return await market_daily_bar_service.status(trade_date)


@router.get("/daily-bars/refresh-history", response_model=MarketDailyBarRefreshHistory)
async def get_market_daily_bar_refresh_history(
    start_date: Date | None = Query(None),
    end_date: Date | None = Query(None),
    status: str | None = Query(None, pattern=r"^(pending|running|success|skipped|failed)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _user: AuthenticatedUser = Depends(require_admin),
):
    """管理员分页查看跨日期刷新历史。"""
    return await market_daily_bar_service.refresh_history(
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/daily-bars/refresh", response_model=MarketDailyBarRefreshResult)
async def refresh_market_daily_bars(
    request: MarketDailyBarRefreshRequest,
    _user: AuthenticatedUser = Depends(require_admin),
):
    """管理员手动刷新、强制重刷或仅重试失败分区。"""
    return await market_daily_bar_service.refresh(request)


@router.post("/daily-bars/delete", response_model=MarketDailyBarDeleteResult)
async def delete_market_daily_bars(
    request: MarketDailyBarDeleteRequest,
    _user: AuthenticatedUser = Depends(require_admin),
):
    """管理员清理指定日期数据，并可在清理后立即重建。"""
    return await market_daily_bar_service.delete_day(
        trade_date=request.trade_date,
        segments=request.segments,
        rebuild=request.rebuild,
        checkpoint=request.checkpoint,
    )


@router.get("/daily-bars/adjustment-status", response_model=MarketAdjustmentFactorStatus)
async def get_market_adjustment_factor_status(
    code: str = Query(..., description="6 位 A 股代码"),
    _user: AuthenticatedUser = Depends(require_admin),
):
    """管理员查看指定 A 股的公司行为与复权因子健康状态。"""
    return await get_adjustment_factor_status(normalize_code(code).raw)


@router.post("/daily-bars/adjustment-refresh", response_model=MarketAdjustmentFactorStatus)
async def refresh_market_adjustment_factors(
    request: MarketAdjustmentFactorRefreshRequest,
    _user: AuthenticatedUser = Depends(require_admin),
):
    """管理员强制复核指定 A 股 XDXR 与仿射复权因子。"""
    return await refresh_adjustment_factors(
        normalize_code(request.code).raw,
        force=request.force,
    )


@router.post("/daily-bars/adjustment-invalidate", response_model=MarketAdjustmentFactorStatus)
async def invalidate_market_adjustment_factors(
    request: MarketAdjustmentFactorInvalidateRequest,
    _user: AuthenticatedUser = Depends(require_admin),
):
    """管理员使指定 A 股衍生因子失效；保留公司行为审计记录。"""
    return await invalidate_adjustment_factors(normalize_code(request.code).raw)


@router.get("/indices", response_model=MarketIndices)
async def get_indices():
    """获取主要大盘指数实时行情。"""
    return await get_indices_service()


@router.get("/index-intraday", response_model=IndexIntradayData)
async def get_index_intraday(
    symbol: str = Query(..., pattern=r"^\d{6}$", description="指数代码，例如 000001"),
):
    """获取主要大盘指数当前交易日分时行情。"""
    return await get_index_intraday_service(symbol)


@router.get("/index-kline", response_model=KlineData)
async def get_index_kline(
    symbol: str = Query(..., description="指数代码，例如 000001"),
    period: str = Query("daily", description="daily / weekly / monthly / annual"),
    start_date: str = Query(""),
    end_date: str = Query(""),
):
    """获取指数 K 线数据。"""
    return await get_index_kline_service(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/volume", response_model=MarketVolumeResponse)
async def get_volume(start_date: str = Query(""), end_date: str = Query("")):
    """获取大盘成交量历史数据。"""
    return await get_market_volume_service(start_date, end_date)


@router.get("/hot-stocks", response_model=list[ThsHotStock])
async def get_hot_stocks():
    """获取热门股排名。"""
    return await get_hot_stocks_service()


@router.get("/hot-rank/ths", response_model=list[ThsHotStock])
async def get_ths_hot_rank():
    """获取同花顺热股榜单。"""
    return await get_hot_stocks_service()


@router.get("/hot-rank/ths/concept", response_model=list[ThsHotPlate])
async def get_ths_hot_concept():
    """获取同花顺热门概念榜。"""
    return await get_ths_hot_concept_service()


@router.get("/hot-rank/ths/industry", response_model=list[ThsHotPlate])
async def get_ths_hot_industry():
    """获取同花顺热门行业榜。"""
    return await get_ths_hot_industry_service()


@router.get("/dragon-tiger", response_model=list[DragonTigerItem])
async def get_dragon_tiger_list(
    report_date: str = Query("", description="报告日期 YYYY-MM-DD，默认当天"),
):
    """获取龙虎榜列表。"""
    return await get_dragon_tiger_list_service(report_date or None)


@router.get("/industry-rankings", response_model=IndustryRankings)
async def get_industry_rankings(
    date: Date | None = Query(None, description="查询日期 YYYY-MM-DD，默认今天"),
):
    """获取行业板块涨跌与资金排名。"""
    return await get_industry_rankings_service(date)


@router.get("/hsgt-flow", response_model=HsgtFlowResponse)
async def get_hsgt_flow():
    """获取沪深股通分钟级资金流向。"""
    return await get_hsgt_flow_service()


@router.get("/hsgt-flow/history", response_model=list[HsgtFlowHistoryItem])
async def get_hsgt_flow_history(days: int = Query(30, description="查询天数")):
    """读取沪深股通历史分钟流向数据。"""
    return await get_hsgt_flow_history_service(days)


@router.get("/northbound-history", response_model=NorthboundHistoryResponse)
async def get_northbound_history(
    page_size: int = Query(500, ge=20, le=3000, description="返回最近交易日数量"),
):
    """获取北向资金与沪深300历史对照数据。"""
    return await get_northbound_history_service(page_size)
