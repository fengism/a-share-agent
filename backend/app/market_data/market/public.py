"""Stable market-wide data capabilities for product modules and Agent tools."""

from app.market_data.market.macro.schemas import MacroAllDataResponse
from app.market_data.market.macro.service import get_macro_all_data, get_macro_data
from app.market_data.market.news import (
    get_market_feed,
    get_market_kuaixun,
    get_market_news,
    get_market_other_news,
)
from app.market_data.market.quotes.dragon_tiger import get_dragon_tiger_detail, get_dragon_tiger_list
from app.market_data.market.quotes.fund_flow import get_hsgt_flow, get_hsgt_flow_history
from app.market_data.market.quotes.hot_rank import get_hot_stocks, get_ths_hot_concept, get_ths_hot_industry
from app.market_data.market.quotes.index_kline import get_index_kline
from app.market_data.market.quotes.indices import get_indices
from app.market_data.market.quotes.schemas import (
    DragonTigerDetail,
    DragonTigerItem,
    HsgtFlowHistoryItem,
    HsgtFlowResponse,
    IndustryRankings,
    MarketStatistics,
    MarketVolumeSeriesItem,
    ThsHotPlate,
    ThsHotStock,
)
from app.market_data.market.quotes.sector import get_industry_rankings
from app.market_data.market.quotes.statistic import get_market_statistics
from app.market_data.market.quotes.volume import get_market_volume, get_realtime_market_volume
from app.market_data.market.twitter import (
    get_twitter_feed,
    get_twitter_user_articles,
    get_twitter_user_content,
    refresh_twitter_feed_now,
    refresh_twitter_feeds,
    refresh_twitter_feeds_sync,
)

__all__ = [
    "DragonTigerDetail",
    "DragonTigerItem",
    "get_dragon_tiger_detail",
    "get_dragon_tiger_list",
    "get_hot_stocks",
    "get_hsgt_flow",
    "get_hsgt_flow_history",
    "get_index_kline",
    "get_indices",
    "get_industry_rankings",
    "get_macro_all_data",
    "get_macro_data",
    "get_market_feed",
    "get_market_kuaixun",
    "get_market_news",
    "get_market_other_news",
    "get_market_statistics",
    "get_market_volume",
    "get_realtime_market_volume",
    "get_ths_hot_concept",
    "get_ths_hot_industry",
    "get_twitter_feed",
    "get_twitter_user_articles",
    "get_twitter_user_content",
    "HsgtFlowHistoryItem",
    "HsgtFlowResponse",
    "IndustryRankings",
    "MacroAllDataResponse",
    "MarketStatistics",
    "MarketVolumeSeriesItem",
    "refresh_twitter_feed_now",
    "refresh_twitter_feeds",
    "refresh_twitter_feeds_sync",
    "ThsHotPlate",
    "ThsHotStock",
]
