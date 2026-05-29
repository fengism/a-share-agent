from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Literal

import requests

from app.models.search_item import NewsSearchItem
from app.services.base.data_provider import BaseDataProvider

logger = logging.getLogger(__name__)

SearchChannel = Literal["report", "announcement", "news"]
QuerySkillId = Literal[
    "hithink-basicinfo-query",
    "hithink-astock-selector",
    "hithink-macro-query",
]

_SEARCH_PATH = "/v1/comprehensive/search"
_QUERY_PATH = "/v1/query2data"
_REPORT_SEARCH_SKILL_ID = "report-search"
_BASIC_INFO_SKILL_ID = "hithink-basicinfo-query"
_STOCK_SELECTOR_SKILL_ID = "hithink-astock-selector"
_MACRO_QUERY_SKILL_ID = "hithink-macro-query"


class IwencaiDataProvider(BaseDataProvider):
    """
    问财数据提供器
    http://ms.10jqka.com.cn/gateway/market/api/v1/skills/square/download?name={slug} 
    """
    
    def __init__(self):
        super().__init__(name="iwencai", source_label="问财")

    @property
    def _base_url(self) -> str:
        try:
            from app.config import get_settings
            settings = get_settings()
            return settings.iwencai_base_url
        except Exception:
            return os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")

    @property
    def _api_key(self) -> str:
        try:
            from app.config import get_settings
            settings = get_settings()
            key = settings.iwencai_api_key
            if key:
                return key
        except Exception:
            pass
        return os.environ.get("IWENCAI_API_KEY", "")

    def _claw_headers(self, call_type: str = "normal") -> dict:
        return {
            "X-Claw-Call-Type": call_type,
            "X-Claw-Skill-Version": "2.0.0",
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": secrets.token_hex(32),
        }

    def _request_headers(self, skill_id: str) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Claw-Skill-Id": skill_id,
            **self._claw_headers(),
        }

    @staticmethod
    def _query_payload(
        query: str,
        page: int,
        limit: int,
        expand_index: bool = True,
    ) -> dict[str, Any]:
        return {
            "query": query,
            "page": str(page),
            "limit": str(limit),
            "is_cache": "1",
            "expand_index": "true" if expand_index else "false",
        }

    def _post_json(self, path: str, payload: dict[str, Any], skill_id: str) -> dict[str, Any]:
        response = requests.post(
            f"{self._base_url}{path}",
            json=payload,
            headers=self._request_headers(skill_id),
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"iwencai HTTP {response.status_code}: {response.text[:200]}")

        data = response.json()
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

        Args:
            query: 搜索关键词
            channel: "report"(研报) / "announcement"(公告) / "news"(新闻)
            size: 返回条数，默认50
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
        """NL 数据查询（结构化字段）。
        例: "贵州茅台 ROE" → DataFrame-like rows
        """
        payload = self._query_payload(query, page, limit)
        data = self._post_json(_QUERY_PATH, payload, _BASIC_INFO_SKILL_ID)
        return data.get("datas") or []

    def select_stocks(self, query: str, page: int = 1, limit: int = 10, expand_index: bool = True) -> list[dict]:
        """
        NL 选股票
        例:
        "今日涨跌幅大于5%" → DataFrame-like rows
        "科技股有哪些" → DataFrame-like rows
        "今日涨停的股票有哪些" → DataFrame-like rows
        """
        payload = self._query_payload(query, page, limit, expand_index)
        data = self._post_json(_QUERY_PATH, payload, _STOCK_SELECTOR_SKILL_ID)
        return data.get("datas") or []

    def query_market_macro(self, query: str, page: int = 1, limit: int = 50, expand_index: bool = True) -> list[dict]:
        """NL 宏观查询（结构化字段）。
        例如：
        "2024年中国GDP" → DataFrame-like rows
        "M2增速" → DataFrame-like rows
        "最近一期CPI" → DataFrame-like rows
        """
        payload = self._query_payload(query, page, limit, expand_index)
        data = self._post_json(_QUERY_PATH, payload, _MACRO_QUERY_SKILL_ID)
        return data.get("datas") or []


    @staticmethod
    def _to_news_search_item(item: dict) -> NewsSearchItem:
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
        """搜索新闻，返回统一 NewsSearchItem 格式。"""
        articles = self.search(query, channel="news", size=size)
        return [self._to_news_search_item(a) for a in self.dedup_articles(articles)]


    @staticmethod
    def dedup_articles(articles: list[dict]) -> list[dict]:
        """同一 uid 仅保留 score 最高的段落"""
        best: dict[str, dict] = {}
        for a in articles:
            uid = a.get("uid", "") or f"{a.get('title','')}|{a.get('publish_date','')}"
            score = float(a.get("score", 0))
            if uid not in best or score > float(best[uid].get("score", 0)):
                best[uid] = a
        return sorted(best.values(), key=lambda x: x.get("publish_date", ""), reverse=True)

    def search_reports(self, query: str, size: int = 50) -> list[dict]:
        """
        搜索研报
        return:
            list[dict]: 研报列表
        例: "茅台最近研报" → DataFrame-like rows
        """
        articles = self.search(query, channel="report", size=size)
        return self.dedup_articles(articles)

    def search_announcements(self, query: str, size: int = 50) -> list[dict]:
        """搜索公告（便捷方法，自动去重）
        return:
            list[dict]: 公告列表
        例: "茅台有哪些公告" → DataFrame-like rows
        """
        articles = self.search(query, channel="announcement", size=size)
        return self.dedup_articles(articles)


iwencai_provider = IwencaiDataProvider()

if __name__ == "__main__":
    print("#######begin report#######")
    #print(iwencai_provider.search_reports("贵州茅台"))
    print("####### news#######")
    print(iwencai_provider.search_news("最近人工智能行业有什么新政策？"))
    
    
    
