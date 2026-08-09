"""分析数据采集。"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.market_data.market.public import get_indices
from app.market_data.stock.public import (
    compute_percentile,
    get_basic_info,
    get_financial_metrics,
    get_kline,
    get_retail_sentiment,
    get_stock_news,
    get_stock_sentiment,
    get_valuation_detail,
)


@dataclass
class AnalysisDataSources:
    basic_info: Callable[..., Awaitable[Any]]
    kline: Callable[..., Awaitable[Any]]
    financial_metrics: Callable[..., Awaitable[Any]]
    valuation_detail: Callable[..., Awaitable[Any]]
    stock_news: Callable[..., Awaitable[Any]]
    stock_sentiment: Callable[..., Awaitable[Any]]
    retail_sentiment: Callable[..., Awaitable[Any]]
    indices: Callable[..., Awaitable[Any]]


analysis_sources = AnalysisDataSources(
    basic_info=get_basic_info,
    kline=get_kline,
    financial_metrics=get_financial_metrics,
    valuation_detail=get_valuation_detail,
    stock_news=get_stock_news,
    stock_sentiment=get_stock_sentiment,
    retail_sentiment=get_retail_sentiment,
    indices=get_indices,
)


@dataclass(frozen=True)
class AnalysisDataBundle:
    basic_info: Any
    kline_data: Any
    financial_metrics: Any | None
    valuation_detail: Any | None
    news_data: list
    sentiment: dict
    retail_sentiment: dict
    market_indices: Any | None


def _resolved(value, fallback):
    return fallback if isinstance(value, Exception) else value


async def collect_analysis_data(code: str, start_date: str) -> AnalysisDataBundle:
    """并行采集个股分析所需数据，并统一处理非关键数据源失败。"""
    (
        basic_info,
        kline_data,
        financial_metrics,
        valuation_detail,
        news_data,
        sentiment,
        retail_sentiment,
        market_indices,
    ) = await asyncio.gather(
        analysis_sources.basic_info(code),
        analysis_sources.kline(code, period="daily", start_date=start_date),
        analysis_sources.financial_metrics(code),
        analysis_sources.valuation_detail(code, compute_percentile),
        analysis_sources.stock_news(code),
        analysis_sources.stock_sentiment(code),
        analysis_sources.retail_sentiment(code),
        analysis_sources.indices(),
        return_exceptions=True,
    )

    basic_info = _resolved(basic_info, None)
    kline_data = _resolved(kline_data, None)
    if not basic_info or not kline_data:
        raise ValueError(f"无法获取股票 {code} 的基本数据")

    return AnalysisDataBundle(
        basic_info=basic_info,
        kline_data=kline_data,
        financial_metrics=_resolved(financial_metrics, None),
        valuation_detail=_resolved(valuation_detail, None),
        news_data=_resolved(news_data, []),
        sentiment=_resolved(sentiment, {}),
        retail_sentiment=_resolved(retail_sentiment, {}),
        market_indices=_resolved(market_indices, None),
    )
