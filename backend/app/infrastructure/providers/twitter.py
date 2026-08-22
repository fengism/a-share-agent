import logging

import requests

from app.configuration import get_settings
from app.constants.http import BROWSER_USER_AGENT
from app.core.news import parse_timestamp
from app.domain.news import NewsSearchItem

logger = logging.getLogger(__name__)


class TwitterDataProvider:
    """Purpose: 通过 fxtwitter API 拉取 Twitter/X 财经账号的媒体与搜索结果，统一封装为 NewsSearchItem。"""
    DEFAULT_BASE_URL = "https://api.fxtwitter.com/2"
    DEFAULT_TIMEOUT = 10
    name = "twitter"

    def __init__(self):
        """初始化 TwitterDataProvider 请求头与会话。"""
        self._headers = {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }
        self._session = requests.Session()
        self._session.trust_env = get_settings().http_trust_env

    @property
    def twitter_feeds(self) -> list[str]:
        """获取当前配置的 Twitter 账号列表。

        Return:
            从运行时配置中读取的 Twitter 账号列表
        """
        return get_settings().twitter_feeds

    def _get_session(self) -> requests.Session:
        """获取当前 Session，并在运行时配置变更后同步 trust_env。"""
        trust_env = get_settings().http_trust_env
        if self._session.trust_env != trust_env:
            self._session.trust_env = trust_env
        return self._session

    def _request(
        self,
        path: str,
        *,
        params: dict | None = None,
        timeout: int | float | None = None,
    ) -> requests.Response:
        """通过复用的 Session 发起 GET 请求并检查状态码。"""
        url = path if path.startswith("http") else f"{self.DEFAULT_BASE_URL}{path}"
        response = self._get_session().request(
            "GET",
            url,
            params=params,
            headers=self._headers,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response

    def _request_json(
        self,
        path: str,
        *,
        params: dict | None = None,
        timeout: int | float | None = None,
    ) -> dict:
        """发起请求并解析 JSON；失败时返回空字典。"""
        try:
            return self._request(path, params=params, timeout=timeout).json()
        except Exception as exc:
            logger.info("Twitter数据获取失败: %s", exc)
            return {}

    def _fetch_posts(self, path: str, *, params: dict | None = None) -> list[dict]:
        """调用 fxtwitter 接口并返回 results 列表（失败时返回空列表）。

        Param:
            path: fxtwitter 接口路径或完整地址
        Return:
            results 字段中的原始记录列表
        """
        return self._request_json(path, params=params).get("results", []) or []

    def fetch_article_by_id(self, id: str) -> dict:
        """根据 Twitter article ID 拉取该文章的最新文章。
        https://api.fxtwitter.com/2/status/{id}?about_account=0&lang=es
        Param:
            id: Twitter article ID 
        Return:
            Dict
        """
        payload = self._request_json(
            f"/status/{id}",
            params={"about_account": "0", "lang": "es"},
        )
        entry = payload.get("status", {}) or {}
        if not entry:
            return {}

        result = {
            "url": entry.get("url", ""),
            "id": entry.get("id", ""),
            "image_url": "",
        }
        # 提取首张图片缩略图
        media = entry.get("media", {}) or {}
        photos = media.get("photos", [])
        if photos:
            result["image_url"] = photos[0].get("url", "")

        article = entry.get("article", {}) or {}
        title = article.get("title", "")
        blocks = article.get("content", {}).get("blocks", [])
        content = ""
        for block in blocks:
            content += block.get("text", "")
            content += "\n"

        result.update(
            {
                "title": title,
                "content": content,
            }
        )
        return result

    def fetch_posts(self) -> list[NewsSearchItem]:
        """获取全部配置账号的最新 Twitter/X 媒体推文和文章。

        Return:
            NewsSearchItem 列表
        """
        return self.fetch_user_articles() + self.fetch_user_posts()

    def fetch_posts_for_users(self, users: list[str]) -> list[NewsSearchItem]:
        """按指定用户列表拉取最新推文和文章。

        Param:
            users: 要拉取的用户名列表。
        Return:
            NewsSearchItem 列表
        """
        if not users:
            return []
        results: list[NewsSearchItem] = []
        for account_name in users:
            for entries, params in [
                (self._fetch_posts(f"/profile/{account_name}/articles", params={"count": "20", "lang": "es"}), "articles"),
                (self._fetch_posts(f"/profile/{account_name}/media", params={"count": "20", "lang": "zh-cn"}), "media"),
            ]:
                for entry in entries:
                    if params == "articles":
                        article = entry.get("article", {}) or {}
                        title = article.get("title", "")
                        content = ""
                        preview_text = article.get("preview_text", "")
                        article_info = self.fetch_article_by_id(entry.get("id", ""))
                        if article_info:
                            content = article_info.get("content", "") or preview_text
                            image_url = article_info.get("image_url", "")
                        else:
                            content = preview_text
                            image_url = ""
                    else:
                        title = str(entry.get("title") or "").strip()
                        content = str(entry.get("text") or "").strip()
                        # 尝试从 media 推文提取图片
                        media = entry.get("media", {}) or {}
                        photos = media.get("photos", [])
                        image_url = photos[0].get("url", "") if photos else ""

                    url = entry.get("url", "")
                    created_at = entry.get("created_timestamp")
                    publish_time = parse_timestamp(created_at)
                    if not title and not content:
                        continue
                    if not title:
                        title = (content or "")[:30]
                    results.append(
                        NewsSearchItem(
                            title=title[:30],
                            content=content or "",
                            image_url=image_url or "",
                            source="Twitter",
                            publish_time=str(publish_time) if publish_time else "",
                            url=url,
                            author=account_name,
                            read_count=0,
                            comment_count=0,
                        )
                    )
        return results

    def fetch_user_articles(self) -> list[NewsSearchItem]:
        """从预置 Twitter 财经账号列表拉取最新媒体推文。

        Return:
            NewsSearchItem 列表
        """
        results: list[NewsSearchItem] = []
        for account_name in self.twitter_feeds:
            entries = self._fetch_posts(
                f"/profile/{account_name}/articles",
                params={"count": "20", "lang": "es"},
            )
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
                image_url = article_info.get("image_url", "")
                if not content:
                    content = preview_text
                created_at = entry.get("created_timestamp")
                publish_time = parse_timestamp(created_at)
                if not title and not content:
                    continue
                # Twitter 推文通常 title 和 content 相同，取 content 作为标题
                if not title:
                    title = content[:30]
                results.append(
                    NewsSearchItem(
                        title=title[:30],
                        content=content,
                        image_url=image_url or "",
                        source="Twitter",
                        publish_time=str(publish_time) if publish_time else "",
                        url=url,
                        author=account_name,
                        read_count=0,
                        comment_count=0,
                    )
                )
        return results

    def fetch_user_articles_raw(self, username: str, count: int = 20) -> list[dict]:
        """拉取指定 Twitter 用户发布的文章（仅 articles），返回原始字典列表。

        每篇文章会通过 fetch_article_by_id 获取完整正文内容。
        此方法仅供 twitter_analysis 服务使用，不保存数据库。

        Param:
            username: Twitter 用户名（不含 @）
            count: 拉取的文章数量上限
        Return:
            包含 title、content、publish_time、url 的字典列表
        """
        results: list[dict] = []
        entries = self._fetch_posts(
            f"/profile/{username}/articles",
            params={"count": str(count), "lang": "es"},
        )
        for entry in entries:
            article = entry.get("article", {}) or {}
            title = article.get("title", "")
            preview_text = article.get("preview_text", "")
            article_info = self.fetch_article_by_id(entry.get("id", ""))
            if not article_info:
                continue
            content = article_info.get("content", "")
            if not content:
                content = preview_text
            created_at = entry.get("created_timestamp")
            publish_time = parse_timestamp(created_at)
            if not title and not content:
                continue
            if not title:
                title = (content or "")[:30]
            results.append({
                "title": title[:30],
                "content": content,
                "publish_time": str(publish_time) if publish_time else "",
                "url": entry.get("url", ""),
            })
        return results

    def fetch_user_posts(self) -> list[NewsSearchItem]:
        """从预置 Twitter 财经账号列表拉取最新媒体推文。

        Return:
            NewsSearchItem 列表
        """
        results: list[NewsSearchItem] = []
        for account_name in self.twitter_feeds:
            entries = self._fetch_posts(
                f"/profile/{account_name}/media",
                params={"count": "20", "lang": "zh-cn"},
            )
            for entry in entries:
                title = str(entry.get("title") or "").strip()
                content = str(entry.get("text") or "").strip()
                url = entry.get("url", "")
                created_at = entry.get("created_timestamp")
                publish_time = parse_timestamp(created_at)
                if not title and not content:
                    continue
                # Twitter 推文通常 title 和 content 相同，取 content 作为标题
                if not title:
                    title = content[:30]
                results.append(
                    NewsSearchItem(
                        title=title[:30],
                        content=content,
                        source="Twitter",
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
        entries = self._fetch_posts(
            "/search",
            params={
                "q": keyword,
                "feed": "latest",
                "count": "30",
                "lang": "zh-cn",
            },
        )
        results: list[NewsSearchItem] = []
        for entry in entries:
            title = str(entry.get("title") or "").strip()
            content = str(entry.get("text") or "").strip()
            url = entry.get("url", "")
            created_at = entry.get("created_timestamp")
            publish_time = parse_timestamp(created_at)
            if not title and not content:
                continue
            if not title:
                title = content[:80]
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source="Twitter",
                    publish_time=str(publish_time) if publish_time else "",
                    url=url,
                    author=entry.get("author_id", ""),
                    read_count=0,
                    comment_count=0,
                )
            )
        return results

twitter_provider = TwitterDataProvider()
