"""市场资讯与智能分析 HTTP API。"""

from fastapi import APIRouter, Depends, Query

from app.api.auth.dependencies import require_active_user
from app.core.exceptions import InvalidRequestError
from app.domain.identity import AuthenticatedUser
from app.domain.news import NewsSearchItem
from app.financial_data.market.public import get_market_feed as get_market_feed_service
from app.financial_data.market.public import get_market_kuaixun as get_market_kuaixun_service
from app.financial_data.market.public import get_market_other_news as get_market_other_news_service
from app.financial_data.market.public import get_twitter_feed as get_twitter_feed_service
from app.financial_data.market.public import refresh_twitter_feed_now
from app.modules.market_intelligence.public import (
    NewsAnalysisResponse,
    TwitterAccountNotConfiguredError,
    TwitterAnalysisResult,
    TwitterFeedRefreshResponse,
    analyze_twitter_user,
)
from app.modules.market_intelligence.public import analyze_market_news as analyze_market_news_service

router = APIRouter()


@router.get("/feed", response_model=list[NewsSearchItem])
async def get_market_feed():
    """获取 24 小时市场新闻流。"""
    return await get_market_feed_service()


@router.get("/kuaixun", response_model=list[NewsSearchItem])
async def get_market_kuaixun():
    """获取 7×24 快讯流。"""
    return await get_market_kuaixun_service()


@router.get("/other-news", response_model=list[NewsSearchItem])
async def get_market_other_news():
    """获取非快讯类新闻。"""
    return await get_market_other_news_service()


@router.get("/twitter-feed", response_model=list[NewsSearchItem])
async def get_twitter_feed():
    """获取 Twitter/X 财经账号的最新推文和文章。"""
    return await get_twitter_feed_service()


@router.post("/twitter-feed/refresh", response_model=TwitterFeedRefreshResponse)
async def refresh_twitter_feed():
    """手动触发 Twitter 资讯刷新。"""
    return await refresh_twitter_feed_now()


@router.get("/news-analysis", response_model=NewsAnalysisResponse)
async def get_news_analysis(user: AuthenticatedUser = Depends(require_active_user)):
    """获取由 LLM 生成的市场资讯综合分析。"""
    return await analyze_market_news_service(user["id"])


@router.get("/twitter-analyze", response_model=TwitterAnalysisResult)
async def get_twitter_analyze(
    username: str = Query(..., description="Twitter 用户名，如 qinbafrank"),
    force_refresh: bool = Query(False, description="忽略缓存并重新生成分析"),
    _user: AuthenticatedUser = Depends(require_active_user),
):
    """分析已配置 Twitter 用户的最新推文和文章并生成 AI 报告。"""
    try:
        return await analyze_twitter_user(username, force_refresh=force_refresh)
    except TwitterAccountNotConfiguredError as error:
        raise InvalidRequestError(str(error), code="invalid_request") from error
