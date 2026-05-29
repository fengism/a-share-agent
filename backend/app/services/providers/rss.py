import feedparser
import time
from app.models.search_item import NewsSearchItem
from app.services.base.data_provider import BaseDataProvider
from app.utils.symbol_utils import contains_stock_reference
from app.utils.news_utils import parse_struct_time_string



class RssDataProvider(BaseDataProvider):
    def __init__(self):
        super().__init__(name="rss", source_label="RSS")

    def fetch_market_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        feed_data = feedparser.parse("https://www.chinanews.com/rss/finance.xml")
        items = feed_data.get("entries", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = str(item.get("summary") or "").strip()
            url = item.get("link", "")
            combined = f"{title}\n{content}"
            if code_name != "" or code != "":
                if not contains_stock_reference(combined, code, code_name):
                    continue
            published_parsed = item.get("published_parsed")
            publish_time = parse_struct_time_string(published_parsed)
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:200],
                    source="cnnews",
                    publish_time=publish_time,
                    url=url,
                    author=item.get("author", ""),
                    read_count=int(item.get("read_count", 0)),
                    comment_count=int(item.get("comment_count", 0)),
                )
            )
        return results



rss_provider = RssDataProvider()

if __name__ == "__main__":
    result = rss_provider.fetch_market_news()
    print(result)
