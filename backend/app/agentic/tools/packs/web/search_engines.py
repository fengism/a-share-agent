"""无需 API Key 的公开网页搜索引擎适配器。"""

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from lxml import html

logger = logging.getLogger(__name__)

_TIME_RANGE_DAYS = {"day": 1, "week": 7, "month": 30, "half_year": 183}
_BING_TIME_FILTERS = {
    "day": 'ex1:"ez1"',
    "week": 'ex1:"ez2"',
    "month": 'ex1:"ez3"',
}
_GOOGLE_TIME_FILTERS = {
    "day": "qdr:d",
    "week": "qdr:w",
    "month": "qdr:m",
    "half_year": "qdr:m6",
}


def _bing_time_filter(time_range: str) -> str | None:
    if time_range == "half_year":
        end_day = int(time.time() // (24 * 60 * 60))
        return f'ex1:"ez5_{end_day - 183}_{end_day}"'
    return _BING_TIME_FILTERS.get(time_range)

class BaseNoApiKeySearchEngine(ABC):
    """无需 API Key 搜索引擎基类"""

    # 类变量 - 子类必须覆盖
    ENGINE_NAME: str = ""           # 引擎名称 (如 "baidu")
    ENGINE_DISPLAY_NAME: str = ""   # 显示名称 (如 "百度搜索")
    SEARCH_URL: str = ""            # 搜索 URL 模板
    REQUIRES_PROXY: bool = False    # 是否需要代理

    def __init__(self, proxy: Optional[str] = None):
        """
        初始化搜索引擎客户端

        Param:
            proxy: 代理地址 (可选)
        """
        self.proxy = proxy or os.getenv("NO_API_KEY_PROXY")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        if self.proxy:
            self.session.proxies = {'http': self.proxy, 'https': self.proxy}

    @abstractmethod
    def build_search_url(self, query: str, **kwargs) -> str:
        """构建搜索 URL"""
        pass

    @abstractmethod
    def parse_results(self, tree: html.HtmlElement) -> List[Dict[str, Any]]:
        """解析 HTML 搜索结果"""
        pass

    def search(
        self,
        query: str,
        max_results: int = 10,
        timeout: int = 15,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        执行搜索

        Param:
            query: 搜索关键词
            max_results: 最大结果数
            timeout: 请求超时时间 (秒)
            **kwargs: 引擎特定参数

        Returns:
            搜索结果列表，每项包含：title, href, body (可能还有其他引擎特定字段)
        """
        search_url = self.build_search_url(query, **kwargs)

        try:
            response = self.session.get(search_url, timeout=timeout)
            response.raise_for_status()
            tree = html.fromstring(response.content)
            results = self.parse_results(tree)

            return results[:max_results]

        except Exception as e:
            raise Exception(f"{self.ENGINE_DISPLAY_NAME} 搜索失败：{str(e)}")

class BaiduSearchNoApi(BaseNoApiKeySearchEngine):
    """百度搜索引擎 (无需 API Key)"""

    ENGINE_NAME = "baidu"
    ENGINE_DISPLAY_NAME = "百度搜索"
    SEARCH_URL = "https://www.baidu.com/s?wd={keyword}"
    REQUIRES_PROXY = False

    def build_search_url(self, query: str, **kwargs) -> str:
        """构建搜索 URL"""
        encoded_query = quote(query)
        search_url = self.SEARCH_URL.replace('{keyword}', encoded_query)
        time_range = kwargs.get("time_range", "any")
        days = _TIME_RANGE_DAYS.get(time_range)
        if days is None:
            return search_url
        end_timestamp = int(time.time())
        start_timestamp = end_timestamp - days * 24 * 60 * 60
        date_filter = quote(
            f"stf={start_timestamp},{end_timestamp}|stftype=1",
            safe="",
        )
        return f"{search_url}&gpc={date_filter}"

    def parse_results(self, tree: html.HtmlElement) -> List[Dict[str, Any]]:
        """解析 HTML 搜索结果"""
        results = []

        # 百度搜索结果容器
        items = tree.xpath("//div[contains(@class, 'result')] | //div[contains(@class, 'c-container')]")

        for item in items:
            try:
                title_elems = item.xpath(".//h3//a//text() | .//a[@class='c-title']//text()")
                href_elems = item.xpath(".//h3//a/@href | .//a[@class='c-title']/@href")
                body_elems = item.xpath(".//div[contains(@class, 'c-abstract')]//text() | .//div[contains(@class, 'abstract')]//text()")

                if title_elems and href_elems:
                    title = ''.join(title_elems).strip()
                    href = ''.join(href_elems).strip()
                    body = ''.join(body_elems).strip() if body_elems else ''

                    if title and href:
                        results.append({
                            'title': title,
                            'href': href,
                            'body': body,
                            'engine': self.ENGINE_NAME
                        })
            except Exception as e:
                logger.debug("解析搜索条目失败: %s", e)
                continue

        return results


class BingCnSearchNoAPI(BaseNoApiKeySearchEngine):
    """Bing 中国搜索引擎 (无需 API Key)"""

    ENGINE_NAME = "bing_cn"
    ENGINE_DISPLAY_NAME = "Bing 中国"
    SEARCH_URL = "https://cn.bing.com/search?q={keyword}&ensearch=0"
    REQUIRES_PROXY = False

    def build_search_url(self, query: str, **kwargs) -> str:
        """构建搜索 URL"""
        encoded_query = quote(query)
        search_url = self.SEARCH_URL.replace('{keyword}', encoded_query)
        if kwargs.get("language", "zh") == "zh":
            search_url = f"{search_url}&setlang=zh-hans&cc=cn"
        time_filter = _bing_time_filter(kwargs.get("time_range", "any"))
        if time_filter is not None:
            search_url = f"{search_url}&filters={quote(time_filter, safe='')}"
        return search_url

    def parse_results(self, tree: html.HtmlElement) -> List[Dict[str, Any]]:
        """解析 HTML 搜索结果"""
        results = []

        items = tree.xpath("//li[contains(@class, 'b_algo')] | //div[contains(@class, 'b_ans')]")

        for item in items:
            try:
                title_elems = item.xpath(".//h2//a//text() | .//a[@class='b_title']//text()")
                href_elems = item.xpath(".//h2//a/@href | .//a[@class='b_title']/@href")
                body_elems = item.xpath(".//div[contains(@class, 'b_caption')]//text() | .//p//text()")

                if title_elems and href_elems:
                    title = ''.join(title_elems).strip()
                    href = ''.join(href_elems).strip()
                    body = ''.join(body_elems).strip() if body_elems else ''

                    if title and href:
                        results.append({
                            'title': title,
                            'href': href,
                            'body': body,
                            'engine': self.ENGINE_NAME
                        })
            except Exception as e:
                logger.debug("解析搜索条目失败: %s", e)
                continue

        return results

class GoogleSearchNoAPI(BaseNoApiKeySearchEngine):
    """Google 搜索引擎 (无需 API Key)"""

    ENGINE_NAME = "google"
    ENGINE_DISPLAY_NAME = "Google 搜索"
    SEARCH_URL = "https://www.google.com/search?q={keyword}"
    REQUIRES_PROXY = True

    def __init__(self, proxy: str = None):
        """初始化 Google 搜索引擎并附加浏览器风格请求头。"""
        super().__init__(proxy)
        # 添加更多请求头以模拟浏览器
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })

    def build_search_url(self, query: str, **kwargs) -> str:
        """构建搜索 URL"""
        encoded_query = quote(query)
        search_url = self.SEARCH_URL.replace('{keyword}', encoded_query)
        if kwargs.get("language", "zh") == "zh":
            search_url = f"{search_url}&hl=zh-CN&lr=lang_zh"
        time_filter = _GOOGLE_TIME_FILTERS.get(kwargs.get("time_range", "any"))
        if time_filter is not None:
            search_url = f"{search_url}&tbs={quote(time_filter, safe='')}"
        return search_url

    def parse_results(self, tree: html.HtmlElement) -> List[Dict[str, Any]]:
        """解析 HTML 搜索结果"""
        results = []

        items = tree.xpath("//div[contains(@class, 'g')] | //div[contains(@class, 'tF2Cxc')]")

        for item in items:
            try:
                title_elems = item.xpath(".//h3//text() | .//div[@class='vvjwJb']//text()")
                href_elems = item.xpath(".//a/@href")
                body_elems = item.xpath(".//div[contains(@class, 'IsZvec')]//text() | .//div[contains(@class, 'VwiK3b')]//text()")

                if title_elems and href_elems:
                    title = ''.join(title_elems).strip()
                    href = ''.join(href_elems).strip()

                    # 过滤无效的 href
                    if not href or not href.startswith('http'):
                        continue

                    body = ''.join(body_elems).strip() if body_elems else ''

                    if title and href:
                        results.append({
                            'title': title,
                            'href': href,
                            'body': body,
                            'engine': self.ENGINE_NAME
                        })
            except Exception as e:
                logger.debug("解析搜索条目失败: %s", e)
                continue

        return results
