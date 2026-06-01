import re

from fastapi import logger
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

    def fetch_zaobao_news(self) -> list[NewsSearchItem]:
        feed_data = feedparser.parse("https://plink.anyfeeder.com/zaobao/realtime/world")
        items = feed_data.get("entries", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = re.sub(r'<[^>]+>', '', str(item.get("description") or "")).strip()
            url = item.get("link", "")
            published_parsed = item.get("published_parsed") or item.get("pubDate")
            publish_time = parse_struct_time_string(published_parsed)
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:200],
                    source="联合早报",
                    publish_time=publish_time,
                    url=url,
                    author=item.get("author", "联合早报"),
                    read_count=0,
                    comment_count=0,
                )
            )
        return results
    
    
    def fetch_36kr_news(self) -> list[NewsSearchItem]:
        feed_data = feedparser.parse("https://36kr.com/feed")
        items = feed_data.get("entries", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = re.sub(r'<[^>]+>', '', str(item.get("summary") or "")).strip()
            url = item.get("link", "")
            published_parsed = item.get("published_parsed") or item.get("pubDate")
            publish_time = parse_struct_time_string(published_parsed)
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source="36氪",
                    publish_time=publish_time,
                    url=url,
                    author=item.get("author", "36氪"),
                    read_count=0,
                    comment_count=0,
                )
            )
        return results


    def fetch_xueqiu_news(self) -> list[NewsSearchItem]:
        feed_data = feedparser.parse("https://plink.anyfeeder.com/weixin/xueqiujinghua")
        items = feed_data.get("entries", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = re.sub(r'<[^>]+>', '', str(item.get("summary") or "")).strip()
            url = item.get("link", "")
            published_parsed = item.get("published_parsed") or item.get("pubDate")
            publish_time = parse_struct_time_string(published_parsed)
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source="雪球",
                    publish_time=publish_time,
                    url=url,
                    author=item.get("author", "雪球"),
                    read_count=0,
                    comment_count=0,
                )
            )
        return results
    

    def fetch_jiemain_news(self) -> list[NewsSearchItem]:
        feed_data = feedparser.parse("https://plink.anyfeeder.com/jiemian/finance")
        items = feed_data.get("entries", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = re.sub(r'<[^>]+>', '', str(item.get("summary") or "")).strip()
            url = item.get("link", "")
            published_parsed = item.get("published_parsed") or item.get("pubDate")
            if not published_parsed:
                published_parsed = time.localtime()
            publish_time = parse_struct_time_string(published_parsed)    
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source="界面新闻",
                    publish_time=publish_time,
                    url=url,
                    author=item.get("author", "界面新闻"),
                    read_count=0,
                    comment_count=0,
                )
            )
        return results
    

    def fetch_eeo_news(self) -> list[NewsSearchItem]:
        feed_data = feedparser.parse("https://plink.anyfeeder.com/weixin/eeo-com-cn")
        items = feed_data.get("entries", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = re.sub(r'<[^>]+>', '', str(item.get("summary") or "")).strip()
            url = item.get("link", "")
            published_parsed = item.get("published_parsed") or item.get("pubDate")
            if not published_parsed:
                published_parsed = time.localtime()
            publish_time = parse_struct_time_string(published_parsed)    
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source="经济观察报",
                    publish_time=publish_time,
                    url=url,
                    author=item.get("author", "经济观察报"),
                    read_count=0,
                    comment_count=0,
                )
            )
        return results
    


rss_provider = RssDataProvider()

if __name__ == "__main__":
    result = rss_provider.fetch_eeo_news()
    print(result)
