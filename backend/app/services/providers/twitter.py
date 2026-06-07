import logging
import re
import feedparser
import requests
from app.services.base.data_provider import BaseDataProvider
from app.models.search_item import NewsSearchItem
from app.utils.news_utils import parse_struct_time_string
from app.constants.http import BROWSER_USER_AGENT

logger = logging.getLogger(__name__)


# 财经相关 Twitter/X 账号
TWITTER_FEEDS = [
    "qinbafrank",
    #aleabitoreddit",
    #168X_Fortune",
    #xiaomustock",
   #"freearkshaw",
    #kikoaifenxi",
]


class TwitterDataProvider(BaseDataProvider):
    """Purpose: 通过 fxtwitter API 拉取 Twitter/X 财经账号的媒体与搜索结果，统一封装为 NewsSearchItem。"""
    def __init__(self):
        """初始化 TwitterDataProvider，设置 name、source_label 与请求头。"""
        super().__init__(name="twitter", source_label="Twitter")
        self.headers = {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

    def _fetch_posts(self, url: str) -> list[dict]:
        """调用 fxtwitter 接口并返回 results 列表（失败时返回空列表）。

        Param:
            url: fxtwitter 接口地址
        Return:
            results 字段中的原始记录列表
        """
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            return r.json().get("results", []) or []
        except Exception as exc:
            logger.info("Twitter数据获取失败: %s", exc)
            return []
        

    def fetch_article_by_id(self, id: str) -> dict:
        """根据 Twitter article ID 拉取该文章的最新文章。
        https://api.fxtwitter.com/2/status/{id}?about_account=0&lang=es
        Param:
            id: Twitter article ID 
        Return:
            Dict
        """
        req_url = f"https://api.fxtwitter.com/2/status/{id}?about_account=0&lang=es"
        r = requests.get(req_url, headers=self.headers, timeout=10)
        if r.status_code != 200:
            logger.info("Twitter数据获取失败: %s", r.status_code)
            return []
        
        entry = r.json().get("status", {}) or {}
      
        result = {
            "url": entry.get("url", ""),
            "id": entry.get("id", ""),
        }
        article = entry.get("article", {}) or {}
        title = article.get("title", "")
        blocks = article.get("content", {}).get("blocks", [])
        content = ""
        for block in blocks:
            content += block.get("text", "")
            content += "\n"

        result.update({
            "title": title,
            "content": content,
        
        })
        return result
        
    def fetch_market_news(self) -> list[NewsSearchItem]:
        """获取最新媒体推文
        
        Return:
            NewsSearchItem 列表
        """
        return self.fetch_user_articles() + self.fetch_user_posts()
    

    def fetch_user_articles(self) -> list[NewsSearchItem]:
        """从预置 Twitter 财经账号列表拉取最新媒体推文。

        Return:
            NewsSearchItem 列表
        """
        results: list[NewsSearchItem] = []
        for account_name in TWITTER_FEEDS:
            feed_url = f"https://api.fxtwitter.com/2/profile/{account_name}/articles?count=20&lang=es"
            entries = self._fetch_posts(feed_url)
            for entry in entries:
                url = entry.get("url", "")
                id = entry.get("id", "")
                article = entry.get("article", {}) or {}
                title = article.get("title", "")
                preview_text = article.get("preview_text", "")
                article_info = self.fetch_article_by_id(id)
                if not article_info:
                    continue
                content = article_info.get("content", "")
                if not content:
                    content = preview_text
                created_at = entry.get("created_timestamp")
                publish_time = self._parse_timestamp(created_at)
                if not title and not content:
                    continue
                # Twitter 推文通常 title 和 content 相同，取 content 作为标题
                if not title:
                    title = content[:30]
                results.append(
                    NewsSearchItem(
                        title=title[:30],
                        content=content,
                        source=f"Twitter",
                        publish_time=str(publish_time) if publish_time else "",
                        url=url,
                        author=account_name,
                        read_count=0,
                        comment_count=0,
                    )
                )
        return results
    

    def fetch_user_posts(self) -> list[NewsSearchItem]:
        """从预置 Twitter 财经账号列表拉取最新媒体推文。

        Return:
            NewsSearchItem 列表
        """
        results: list[NewsSearchItem] = []
        for account_name in TWITTER_FEEDS:
            feed_url = f"https://api.fxtwitter.com/2/profile/{account_name}/media?count=20&lang=zh-cn"
            entries = self._fetch_posts(feed_url)
            for entry in entries:
                title = str(entry.get("title") or "").strip()
                content = str(entry.get("text") or "").strip()
                url = entry.get("url", "")
                created_at = entry.get("created_timestamp")
                publish_time = self._parse_timestamp(created_at)
                if not title and not content:
                    continue
                # Twitter 推文通常 title 和 content 相同，取 content 作为标题
                if not title:
                    title = content[:30]
                results.append(
                    NewsSearchItem(
                        title=title[:30],
                        content=content,
                        source=f"Twitter",
                        publish_time=str(publish_time) if publish_time else "",
                        url=url,
                        author=account_name,
                        read_count=0,
                        comment_count=0,
                    )
                )
        return results

    def search(self, keyword: str) -> list[NewsSearchItem]:
        """按关键词搜索 Twitter 推文并返回 NewsSearchItem 列表。

        Param:
            keyword: 搜索关键词
        Return:
            NewsSearchItem 列表
        """
        req_url = f"https://api.fxtwitter.com/2/search?q={keyword}&feed=latest&count=30&lang=zh-cn"
        entries = self._fetch_posts(req_url)
        results: list[NewsSearchItem] = []
        for entry in entries:
            title = str(entry.get("title") or "").strip()
            content = str(entry.get("text") or "").strip()
            url = entry.get("url", "")
            created_at = entry.get("created_timestamp")
            publish_time = self._parse_timestamp(created_at)
            if not title and not content:
                continue
            if not title:
                title = content[:80]
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source=f"Twitter",
                    publish_time=str(publish_time) if publish_time else "",
                    url=url,
                    author=entry.get("author_id", ""),
                    read_count=0,
                    comment_count=0,
                )
            )
        return results 

twitter_provider = TwitterDataProvider()