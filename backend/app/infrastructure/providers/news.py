import logging
import re
import time

import feedparser

from app.core.market import contains_stock_reference
from app.core.news import parse_timestamp
from app.domain.news import NewsSearchItem
from app.infrastructure.http.client import provider_request as request

logger = logging.getLogger(__name__)


def parse_struct_time_string(value) -> str:
    """Format a feedparser struct_time value or its repr."""
    if hasattr(value, "tm_year"):
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", value)
        except (TypeError, ValueError):
            return ""

    text = str(value or "").strip()
    pattern = (
        r"tm_year=(\d+),\s*"
        r"tm_mon=(\d+),\s*"
        r"tm_mday=(\d+),\s*"
        r"tm_hour=(\d+),\s*"
        r"tm_min=(\d+),\s*"
        r"tm_sec=(\d+)"
    )
    match = re.search(pattern, text)
    if not match:
        return ""
    year, month, day, hour, minute, second = map(int, match.groups())
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"



class NewsDataProvider:
    """Purpose: 通过 RSS/Atom 订阅源拉取并解析财经新闻媒体内容，输出统一的 NewsSearchItem。

    注意：RSS 解析使用 feedparser（同步库），在异步上下文中应通过 asyncio.to_thread 调用。
    """
    name = "rss"

    def _parse_rss_feed(
        self,
        url: str,
        source: str,
        author: str = "",
        content_field: str = "summary",
        fallback_pub_time: bool = False,
    ) -> list[NewsSearchItem]:
        """Parse a standard RSS feed into NewsSearchItem list.

        Param:
            url: RSS 订阅源地址
            source: 数据来源标识
            author: 默认作者
            content_field: 正文字段名
            fallback_pub_time: 是否在缺失发布时间时回退到本地时间
        Return:
            NewsSearchItem 列表
        """
        feed_data = feedparser.parse(url)
        items = feed_data.get("entries", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            raw_content = str(item.get(content_field) or "")
            content = re.sub(r'<[^>]+>', '', raw_content).strip()
            link = item.get("link", "")
            published_parsed = item.get("published_parsed") or item.get("pubDate")
            if not published_parsed and fallback_pub_time:
                published_parsed = time.localtime()
            publish_time = parse_struct_time_string(published_parsed)
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:200],
                    source=source,
                    publish_time=publish_time,
                    url=link,
                    author=item.get("author") or author,
                    read_count=0,
                    comment_count=0,
                )
            )
        return results

    def fetch_china_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """从中国新闻网财经 RSS 拉取市场新闻，可按股票代码/名称过滤。

        Param:
            code: 可选，6 位股票代码
            code_name: 可选，股票名称
        Return:
            NewsSearchItem 列表
        """
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
        """获取联合早报全球实时新闻（RSS 订阅源）。

        Return:
            NewsSearchItem 列表
        """
        return self._parse_rss_feed(
            "https://plink.anyfeeder.com/zaobao/realtime/world",
            source="联合早报", author="联合早报", content_field="description",
        )

    def fetch_36kr_news(self) -> list[NewsSearchItem]:
        """获取 36氪 资讯（RSS 订阅源）。

        Return:
            NewsSearchItem 列表
        """
        return self._parse_rss_feed(
            "https://36kr.com/feed",
            source="36氪", author="36氪",
        )

    def fetch_xueqiu_news(self) -> list[NewsSearchItem]:
        """获取雪球精华（RSS 订阅源）。

        Return:
            NewsSearchItem 列表
        """
        return self._parse_rss_feed(
            "https://plink.anyfeeder.com/weixin/xueqiujinghua",
            source="雪球", author="雪球",
        )

    def fetch_jiemain_news(self) -> list[NewsSearchItem]:
        """获取界面新闻财经（RSS 订阅源），缺失发布时间时回退到本地时间。

        Return:
            NewsSearchItem 列表
        """
        return self._parse_rss_feed(
            "https://plink.anyfeeder.com/jiemian/finance",
            source="界面新闻", author="界面新闻", fallback_pub_time=True,
        )

    def fetch_eeo_news(self) -> list[NewsSearchItem]:
        """获取经济观察报（RSS 订阅源），缺失发布时间时回退到本地时间。

        Return:
            NewsSearchItem 列表
        """
        return self._parse_rss_feed(
            "https://plink.anyfeeder.com/weixin/eeo-com-cn",
            source="经济观察报", author="经济观察报", fallback_pub_time=True,
        )

    def fetch_wallstreetcn_hot_article(self) -> list[NewsSearchItem]:
        """获取华尔街见闻最热文章（Hot Articles API）。

        Return:
            NewsSearchItem 列表，按热度排序
        """
        url = "https://api-one-wscn.awtmt.com/apiv1/content/articles/hot"
        try:
            resp = request("GET", url, params={"period": "all"},
                           headers={"Content-Type": "application/json"}, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("华尔街见闻最热文章获取失败: %s", e)
            return []
        data = resp.json()
        items = data.get("data", {}).get("day_items", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            publish_time = parse_timestamp(item.get("display_time", ""))
            results.append(
                NewsSearchItem(
                    title=title,
                    content="",
                    source="华尔街见闻 - 最热文章",
                    publish_time=publish_time.isoformat(sep=" ") if publish_time else "",
                    url=item.get("uri", ""),
                    author="华尔街见闻",
                    read_count=int(item.get("pageviews", 0)),
                    comment_count=int(item.get("comment_count", 0)),
                )
            )
        return results

    def fetch_wallstreetcn_news(self, limit: int = 10) -> list[NewsSearchItem]:
        """获取华尔街见闻最新资讯（Information Flow API，article 类型）。

        Param:
            limit: 返回条数，默认 10
        Return:
            NewsSearchItem 列表
        """
        url = "https://api-one-wscn.awtmt.com/apiv1/content/information-flow"
        params = {"channel": "global", "accept": "article", "limit": limit}
        try:
            resp = request("GET", url, params=params, headers={"Content-Type": "application/json"}, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("华尔街见闻资讯获取失败: %s", e)
            return []
        data = resp.json()
        items = data.get("data", {}).get("items", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            resource = item.get("resource", {})
            title = str(resource.get("title") or "").strip()
            content = str(resource.get("content_short") or "").strip()
            if not title:
                title = content[:30] + "..." if len(content) > 30 else content
            article_url = resource.get("uri", "")
            publish_time = parse_timestamp(resource.get("display_time", ""))
            author_info = resource.get("author", {})
            author = "华尔街见闻"
            if isinstance(author_info, dict):
                author = author_info.get("display_name") or author_info.get("name") or "华尔街见闻"
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source="华尔街见闻",
                    publish_time=publish_time.isoformat(sep=" ") if publish_time else "",
                    url=article_url,
                    author=author,
                    read_count=0,
                    comment_count=0,
                )
            )
        return results

    def fetch_wallstreetcn_kuaixun(self) -> list[NewsSearchItem]:
        """获取华尔街见闻的 7x24 快讯数据。

        Return:
            NewsSearchItem 列表
        """
        reqUrl = "https://api-one-wscn.awtmt.com/apiv1/content/lives"
        payload = {
            "channel": "global-channel",
            "client": "pc",
            "limit": 20,
            "first_page": True,
            "accept": "live,vip-live",
        }
        headers = {
            "Content-Type": "application/json",
        }
        req = request("GET", reqUrl, params=payload, headers=headers, timeout=10)
        if req.status_code != 200:
            logger.error(f"获取华尔街见闻失败: error={req.status_code}, content={req.text}")
            raise RuntimeError(f"获取华尔街见闻失败: {req.status_code}")
        data = req.json()
        items = data.get("data", {}).get("items", []) or []
        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = re.sub(r'<[^>]+>', '', str(item.get("content_text") or "")).strip()
            if not title:
                title = content[:30] + "..." if len(content) > 30 else content
            url = item.get("uri", "")
            publish_time = parse_timestamp(item.get("display_time", ""))
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source="华尔街见闻7x24快讯",
                    publish_time=publish_time.isoformat(sep=" ") if publish_time else "",
                    url=url,
                    author=self._extract_author(item),
                    read_count=0,
                    comment_count=0,
                )
            )
        return results

    @staticmethod
    def _extract_author(item: dict) -> str:
        """Extract author string from RSS item, handling dict author objects.

        Param:
            item: RSS 条目字典
        Return:
            作者字符串，缺失时返回 "华尔街见闻"
        """
        author = item.get("author", "华尔街见闻")
        if isinstance(author, str):
            return author or "华尔街见闻"
        if isinstance(author, dict):
            return author.get("display_name") or author.get("name") or "华尔街见闻"
        return "华尔街见闻"
    
    def fetch_market_kuaixun(self) -> list[NewsSearchItem]:
        """获取 7x24 快讯数据。

        Return:
            NewsSearchItem 列表
        """
        return self.fetch_wallstreetcn_kuaixun()

news_provider = NewsDataProvider()
