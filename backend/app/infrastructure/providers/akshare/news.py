"""AkShare 新闻与人气排名能力。"""

import pandas as pd

from app.domain.news import NewsSearchItem
from app.infrastructure.providers.akshare.loader import ak


def fetch_stock_news(code: str) -> list[NewsSearchItem]:
    results: list[NewsSearchItem] = []
    frame = ak.stock_news_em(symbol=code)
    if frame is None or frame.empty:
        return results
    for _, row in frame.head(20).iterrows():
        results.append(
            NewsSearchItem(
                title=str(row.get("新闻标题", "")),
                content=str(row.get("新闻内容", "")),
                source=str(row.get("文章来源", "")),
                publish_time=str(row.get("发布时间", "")),
                url=str(row.get("新闻链接", "")),
                author=str(row.get("作者", "")),
                read_count=int(row.get("阅读量", 0)),
                comment_count=int(row.get("评论量", 0)),
            )
        )
    return results


def fetch_hot_rank_detail(symbol: str) -> pd.DataFrame:
    return ak.stock_hot_rank_detail_em(symbol=symbol)
