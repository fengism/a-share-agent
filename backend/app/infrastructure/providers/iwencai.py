from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from typing import Any, Literal

from app.configuration import get_effective_settings
from app.configuration.schema import Settings
from app.core.exceptions import ApplicationError
from app.domain.news import NewsSearchItem
from app.infrastructure.http.client import get_provider_session as _get_session

logger = logging.getLogger(__name__)

SearchChannel = Literal["report", "announcement", "news"]
_SEARCH_PATH = "/v1/comprehensive/search"
_QUERY_PATH = "/v1/query2data"
_REPORT_SEARCH_SKILL_ID = "report-search"
_BASIC_INFO_SKILL_ID = "hithink-basicinfo-query"
_STOCK_SELECTOR_SKILL_ID = "hithink-astock-selector"
_MACRO_QUERY_SKILL_ID = "hithink-macro-query"
_SKILL_VERSIONS = {
    _REPORT_SEARCH_SKILL_ID: "1.0.0",
    _BASIC_INFO_SKILL_ID: "1.0.0",
    _STOCK_SELECTOR_SKILL_ID: "1.0.0",
    _MACRO_QUERY_SKILL_ID: "1.0.0",
}


class IwencaiConfigurationError(ApplicationError):
    default_code = "iwencai_not_configured"


class IwencaiAuthenticationError(ApplicationError):
    default_code = "iwencai_auth_failed"


class IwencaiDataProvider:
    """
    问财数据提供器
    http://ms.10jqka.com.cn/gateway/market/api/v1/skills/square/download?name={slug} 
    """
    
    name = "iwencai"

    def __init__(
        self,
        settings_provider: Callable[[], Settings],
        session_provider: Callable[[], Any],
    ):
        self._settings_provider = settings_provider
        self._session_provider = session_provider

    def _claw_headers(self, skill_id: str, call_type: str = "normal") -> dict:
        """构造问财 Claw 协议所需的自定义头（包含 trace_id）。

        Param:
            skill_id: 问财 skill 标识
            call_type: 调用类型标识
        Return:
            包含 X-Claw-* 系列头的字典
        """
        try:
            skill_version = _SKILL_VERSIONS[skill_id]
        except KeyError as error:
            raise IwencaiConfigurationError(f"问财 Skill {skill_id} 未配置版本") from error
        return {
            "X-Claw-Call-Type": call_type,
            "X-Claw-Skill-Version": skill_version,
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": secrets.token_hex(32),
        }

    def _request_headers(self, skill_id: str, *, settings: Settings) -> dict:
        """构造问财请求头（合并鉴权、Claw 头与 skill_id）。

        Param:
            skill_id: 问财 skill 标识
        Return:
            完整的请求头字典
        """
        api_key = settings.iwencai_api_key.strip()
        if not api_key:
            raise IwencaiConfigurationError("问财 API Key 未配置，请在设置中填写；自定义地址不能复用全局 Key")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Claw-Skill-Id": skill_id,
            **self._claw_headers(skill_id),
        }

    @staticmethod
    def _query_payload(
        query: str,
        page: int,
        limit: int,
        expand_index: bool = True,
    ) -> dict[str, Any]:
        """构造问财 query2data 接口的请求体。

        Param:
            query: 自然语言查询
            page: 页码
            limit: 每页条数
            expand_index: 是否展开指数数据
        Return:
            问财 query2data 接口的 payload 字典
        """
        return {
            "query": query,
            "page": str(page),
            "limit": str(limit),
            "is_cache": "1",
            "expand_index": "true" if expand_index else "false",
        }

    def _post_json(self, path: str, payload: dict[str, Any], skill_id: str) -> dict[str, Any]:
        """向问财 OpenAPI 发起 POST 请求并校验返回结果。

        Param:
            path: 接口路径
            payload: 请求体
            skill_id: 问财 skill 标识
        Return:
            问财接口返回的 data 字段
        """
        # Read URL and key from one snapshot; never restore an isolated key from env.
        settings = self._settings_provider()
        headers = self._request_headers(skill_id, settings=settings)
        response = self._session_provider().post(
            f"{settings.iwencai_base_url}{path}",
            json=payload,
            headers=headers,
            timeout=30,
        )
        if response.status_code in {401, 403}:
            raise IwencaiAuthenticationError(
                f"问财鉴权失败（HTTP {response.status_code}），"
                f"请检查设置中的 API Key 是否有效，并确认当前 Key 已开通 {skill_id}"
            )
        if response.status_code != 200:
            raise RuntimeError(f"iwencai HTTP {response.status_code}: {response.text[:200]}")

        data = response.json()
        if data.get("status_code") in {401, 403}:
            raise IwencaiAuthenticationError(
                f"问财鉴权失败（状态码 {data['status_code']}），"
                f"请检查设置中的 API Key 是否有效，并确认当前 Key 已开通 {skill_id}"
            )
        if data.get("status_code", 0) != 0:
            raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
        return data

    def search(
        self,
        query: str,
        channel: SearchChannel = "report",
        size: int = 50,
    ) -> list[dict]:
        """语义搜索研报/公告/新闻。

        Param:
            query: 搜索关键词
            channel: "report"(研报) / "announcement"(公告) / "news"(新闻)
            size: 返回条数，默认50

        Param:
            query: 搜索关键词
            channel: 搜索频道
            size: 返回条数
        Return:
            问财搜索结果的 data 列表
        """
        payload = {
            "channels": [channel],
            "app_id": "AIME_SKILL",
            "query": query,
            "size": size,
        }
        data = self._post_json(_SEARCH_PATH, payload, _REPORT_SEARCH_SKILL_ID)
        return data.get("data") or []

    def query_stock_data(self, query: str, page: int = 1, limit: int = 50) -> list[dict]:
        """NL 数据查询（结构化字段）。例: "贵州茅台 ROE" → DataFrame-like rows

        Param:
            query: 自然语言查询
            page: 页码
            limit: 每页条数
        Return:
            问财 datas 列表
        """
        payload = self._query_payload(query, page, limit)
        data = self._post_json(_QUERY_PATH, payload, _BASIC_INFO_SKILL_ID)
        return data.get("datas") or []

    def select_stocks(self, query: str, page: int = 1, limit: int = 10, expand_index: bool = True) -> list[dict]:
        """NL 选股票。

        Param:
            query: 自然语言选股条件
            page: 页码
            limit: 每页条数
            expand_index: 是否展开指数数据
        Return:
            命中的股票列表
        """
        payload = self._query_payload(query, page, limit, expand_index)
        data = self._post_json(_QUERY_PATH, payload, _STOCK_SELECTOR_SKILL_ID)
        return data.get("datas") or []

    def query_market_macro(self, query: str, page: int = 1, limit: int = 50, expand_index: bool = True) -> list[dict]:
        """NL 宏观查询（结构化字段）。

        Param:
            query: 自然语言宏观查询
            page: 页码
            limit: 每页条数
            expand_index: 是否展开指数数据
        Return:
            宏观数据行列表
        """
        payload = self._query_payload(query, page, limit, expand_index)
        data = self._post_json(_QUERY_PATH, payload, _MACRO_QUERY_SKILL_ID)
        return data.get("datas") or []

    @staticmethod
    def _to_news_search_item(item: dict) -> NewsSearchItem:
        """将问财搜索结果 item 转换为统一的 NewsSearchItem。

        Param:
            item: 问财搜索返回的单条结果字典
        Return:
            NewsSearchItem 对象
        """
        extra = item.get("extra") or {}
        return NewsSearchItem(
            title=str(item.get("title") or "").strip(),
            content=str(item.get("summary") or item.get("source_original") or "")[:500],
            source=extra.get("publish_source") or extra.get("real_publish_source") or "问财",
            publish_time=str(item.get("publish_date") or ""),
            url=str(item.get("url") or ""),
            author=str(item.get("name") or ""),
            read_count=0,
            comment_count=0,
        )

    def search_news(self, query: str, size: int = 10) -> list[NewsSearchItem]:
        """搜索新闻，返回统一 NewsSearchItem 格式。

        Param:
            query: 新闻搜索关键词
            size: 返回条数
        Return:
            去重后的 NewsSearchItem 列表
        """
        articles = self.search(query, channel="news", size=size)
        return [self._to_news_search_item(a) for a in self.dedup_articles(articles)]

    @staticmethod
    def dedup_articles(articles: list[dict]) -> list[dict]:
        """同一 uid 仅保留 score 最高的段落。

        Param:
            articles: 问财文章列表
        Return:
            按发布时间倒序、去重后的文章列表
        """
        best: dict[str, dict] = {}
        for a in articles:
            uid = a.get("uid", "") or f"{a.get('title','')}|{a.get('publish_date','')}"
            score = float(a.get("score", 0))
            if uid not in best or score > float(best[uid].get("score", 0)):
                best[uid] = a
        return sorted(best.values(), key=lambda x: x.get("publish_date", ""), reverse=True)

    def search_reports(self, query: str, size: int = 50) -> list[dict]:
        """搜索研报（去重后返回）。例: "茅台最近研报" → DataFrame-like rows

        Param:
            query: 研报搜索关键词
            size: 返回条数
        Return:
            研报列表
        """
        articles = self.search(query, channel="report", size=size)
        return self.dedup_articles(articles)

    def search_announcements(self, query: str, size: int = 50) -> list[dict]:
        """搜索公告（便捷方法，自动去重）。例: "茅台有哪些公告" → DataFrame-like rows

        Param:
            query: 公告搜索关键词
            size: 返回条数
        Return:
            公告列表
        """
        articles = self.search(query, channel="announcement", size=size)
        return self.dedup_articles(articles)

iwencai_provider = IwencaiDataProvider(get_effective_settings, _get_session)
