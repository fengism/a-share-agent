"""无需 API Key 的公开网页搜索引擎适配器。"""

import logging
import os
import re
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlsplit

import requests
from lxml import html

from app.infrastructure.http.decode import decode_html_response

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
_BAIDU_COOKIE_TTL_SECONDS = 1800.0
# 百度首页 URL；用于换取 Cookie，同时作为搜索请求的 Referer。
_BAIDU_HOME_URL = "https://www.baidu.com/"
# 命中安全验证时页面只有几 KB，正常结果页远大于此。
_BAIDU_CHALLENGE_MAX_BYTES = 50_000
# 百度对浏览器指纹非常敏感：同一出口 IP 下桌面 Chrome UA 可能被持续拦截，
# 而移动端 UA 仍可正常返回。两套档案轮换使用，配合 Cookie 预热显著降低空结果概率。
# 请求头必须成套使用——给 Safari UA 配上 Chrome 的 Sec-Fetch-User 同样会被判为伪造。
_BAIDU_PROFILES: tuple[dict[str, str], ...] = (
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    },
)


def _bing_time_filter(time_range: str) -> str | None:
    if time_range == "half_year":
        end_day = int(time.time() // (24 * 60 * 60))
        return f'ex1:"ez5_{end_day - 183}_{end_day}"'
    return _BING_TIME_FILTERS.get(time_range)


_baidu_cookie_lock = threading.Lock()
_baidu_cookie_cache: dict[int, tuple[float, dict[str, str]]] = {}
_baidu_good_profile = [0]


def _cached_baidu_cookies(profile: int) -> dict[str, str]:
    """复用百度首页换来的 Cookie。

    百度对没有 ``BAIDUID`` 的裸请求直接返回「百度安全验证」空壳页；而首页有 700KB+
    重，每次搜索都预热一次太浪费，所以按 TTL 缓存进程内共享的 Cookie。

    Cookie 必须按浏览器指纹分桶：``BAIDUID``/``BIDUPSID`` 与 UA 绑定，混用会直接触发验证。
    """
    with _baidu_cookie_lock:
        cached = _baidu_cookie_cache.get(profile)
    if cached and time.monotonic() - cached[0] < _BAIDU_COOKIE_TTL_SECONDS:
        return dict(cached[1])
    return {}


def _remember_baidu_cookies(session: requests.Session, profile: int) -> None:
    cookies = {cookie.name: cookie.value or "" for cookie in session.cookies}
    if not cookies:
        return
    with _baidu_cookie_lock:
        _baidu_cookie_cache[profile] = (time.monotonic(), cookies)


def _forget_baidu_cookies(profile: int) -> None:
    with _baidu_cookie_lock:
        _baidu_cookie_cache.pop(profile, None)


def _preferred_baidu_profile() -> int:
    """上次成功返回结果的指纹；默认桌面版。"""
    with _baidu_cookie_lock:
        return _baidu_good_profile[0]


def _mark_baidu_profile(profile: int) -> None:
    with _baidu_cookie_lock:
        _baidu_good_profile[0] = profile


def _join_text(nodes) -> str:
    """把散落的文本节点拼回原句。

    百度用 ``<em>`` 包裹命中的关键词，节点边界正好切在词中间，所以必须无分隔符拼接；
    但 HTML 源码里标签之间又有换行缩进，拼接后需要把连续空白压成单个空格再 strip。
    """
    return re.sub(r"\s+", " ", "".join(node for node in nodes if node)).strip()


def _baidu_real_url(item: html.HtmlElement, href: str) -> str:
    """取结果条目的真实地址。

    百度 ``h3 a`` 上的 ``href`` 是 ``www.baidu.com/link?url=...`` 之类的跳转地址，
    既不能直接展示（前端看到的是一大串无意义 token），也不适合做来源去重；
    真实地址放在容器的 ``mu`` 属性里。
    """
    for attribute in ("mu", "data-landurl", "data-url"):
        candidate = (item.get(attribute) or "").strip()
        if candidate.startswith(("http://", "https://")):
            return candidate
    return href


def _is_baidu_internal(url: str) -> bool:
    """判断是否百度站内地址（AI 摘要卡、相关搜索、知道/文库等），这类不是可用证据。"""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return True
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if hostname != "baidu.com" and not hostname.endswith(".baidu.com"):
        return False
    # /link?url=... 是可跟随的跳转链接，交给上层保留。
    return not parsed.path.startswith("/link")


class BaseNoApiKeySearchEngine(ABC):
    """无需 API Key 搜索引擎基类"""

    # 类变量 - 子类必须覆盖
    ENGINE_NAME: str = ""  # 引擎名称 (如 "baidu")
    ENGINE_DISPLAY_NAME: str = ""  # 显示名称 (如 "百度搜索")
    SEARCH_URL: str = ""  # 搜索 URL 模板
    REQUIRES_PROXY: bool = False  # 是否需要代理

    def __init__(self, proxy: Optional[str] = None):
        """
        初始化搜索引擎客户端

        Param:
            proxy: 代理地址 (可选)
        """
        self.proxy = proxy or os.getenv("NO_API_KEY_PROXY")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

    @abstractmethod
    def build_search_url(self, query: str, **kwargs) -> str:
        """构建搜索 URL"""
        pass

    @abstractmethod
    def parse_results(self, tree: html.HtmlElement) -> List[Dict[str, Any]]:
        """解析 HTML 搜索结果"""
        pass

    def _fetch_tree(self, search_url: str, timeout: int) -> html.HtmlElement:
        """请求并解析搜索结果页。"""
        response = self.session.get(search_url, timeout=timeout)
        response.raise_for_status()
        # 必须先按声明的字符集解码成 str：lxml 收到 bytes 且无显式编码时会退回
        # latin-1，导致 UTF-8 搜索结果整体变成乱码（贵州 → è´µå·）。
        return html.fromstring(decode_html_response(response))

    def search(self, query: str, max_results: int = 10, timeout: int = 15, **kwargs) -> List[Dict[str, Any]]:
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
        tree = self._fetch_tree(self.build_search_url(query, **kwargs), timeout)
        results = self.parse_results(tree)
        return results[:max_results]


class BaiduSearchNoApi(BaseNoApiKeySearchEngine):
    """百度搜索引擎 (无需 API Key)"""

    ENGINE_NAME = "baidu"
    ENGINE_DISPLAY_NAME = "百度搜索"
    SEARCH_URL = "https://www.baidu.com/s?wd={keyword}"
    REQUIRES_PROXY = False

    def __init__(self, proxy: Optional[str] = None):
        """初始化百度会话，附带浏览器导航请求头并复用已缓存的 Cookie。"""
        super().__init__(proxy)
        self._profile = 0
        self._warm_profile = -1
        self._apply_profile(_preferred_baidu_profile())

    def _apply_profile(self, index: int) -> None:
        """切换到第 index 套浏览器指纹，并载入该指纹对应的 Cookie。"""
        index %= len(_BAIDU_PROFILES)
        # 指纹是成套的：切档案时必须把上一套的 Sec-Fetch-* 一并摘掉。
        stale = [header for header in self.session.headers if header.startswith("Sec-Fetch-")]
        for header in stale:
            del self.session.headers[header]
        self.session.headers.update(_BAIDU_PROFILES[index])
        self._profile = index
        self.session.cookies.clear()
        self.session.cookies.update(_cached_baidu_cookies(index))
        self._warm_profile = -1

    def _ensure_cookies(self, timeout: int) -> None:
        """确保当前指纹的会话带上 ``BAIDUID``，否则结果页会被替换成安全验证。"""
        if self._warm_profile == self._profile and self.session.cookies.get("BAIDUID"):
            return
        self._warm_profile = self._profile
        if self.session.cookies.get("BAIDUID"):
            return
        try:
            self.session.get(_BAIDU_HOME_URL, timeout=timeout)
        except requests.RequestException as exc:
            logger.debug("百度首页预热失败: %s", exc)
        _remember_baidu_cookies(self.session, self._profile)

    def build_search_url(self, query: str, **kwargs) -> str:
        """构建搜索 URL"""
        encoded_query = quote(query)
        search_url = self.SEARCH_URL.replace("{keyword}", encoded_query)
        # rn 决定单页条数：默认只有 10 条，过滤掉站内卡片后不够返回给上层。
        try:
            requested = int(kwargs.get("max_results") or 10)
        except (TypeError, ValueError):
            requested = 10
        page_size = min(max(requested * 2, 10), 20)
        # tn=baiduhome_pg 锁定服务端渲染的经典版式：移动端 UA 默认拿到的是纯 JS 卡片，
        # 里面连 <a href> 都没有，正则/xpath 解析不到任何结果。
        search_url = f"{search_url}&ie=utf-8&tn=baiduhome_pg&rn={page_size}"
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

    def _search_once(
        self, query: str, max_results: int, timeout: int, kwargs: dict[str, Any], profile: int
    ) -> List[Dict[str, Any]]:
        self._apply_profile(profile)
        self._ensure_cookies(timeout)
        search_url = self.build_search_url(query, max_results=max_results, **kwargs)
        self.session.headers["Referer"] = _BAIDU_HOME_URL
        response = self.session.get(search_url, timeout=timeout)
        response.raise_for_status()
        content = getattr(response, "content", b"")
        if len(content) < _BAIDU_CHALLENGE_MAX_BYTES:
            logger.info("百度搜索命中安全验证页（%s 字节），按空结果处理", len(content))
            return []
        _remember_baidu_cookies(self.session, self._profile)
        return self.parse_results(html.fromstring(decode_html_response(response)))[:max_results]

    def search(self, query: str, max_results: int = 10, timeout: int = 15, **kwargs) -> List[Dict[str, Any]]:
        """执行搜索。

        百度会把部分出口 IP + 指纹组合判为机器人。哪套指纹能用因 IP 而异，所以记住上次
        成功的那套优先尝试，失败再依次换指纹、刷新 Cookie 重试；仍拿不到结果就交由上层降级。
        """
        preferred = _preferred_baidu_profile()
        order = [preferred, *(index for index in range(len(_BAIDU_PROFILES)) if index != preferred)]
        for profile in order:
            results = self._search_once(query, max_results, timeout, kwargs, profile)
            if results:
                _mark_baidu_profile(profile)
                return results
        _forget_baidu_cookies(order[0])
        return self._search_once(query, max_results, timeout, kwargs, order[0])

    def parse_results(self, tree: html.HtmlElement) -> List[Dict[str, Any]]:
        """解析 HTML 搜索结果"""
        results = []

        # 百度搜索结果容器
        items = tree.xpath("//div[contains(@class, 'c-container')]")

        for item in items:
            try:
                anchor = item.xpath(".//h3//a") or item.xpath(".//a[@class='c-title']")
                if not anchor:
                    continue
                link = anchor[0]
                title = _join_text(link.itertext())
                href = _baidu_real_url(item, (link.get("href") or "").strip())
                if not title or not href or _is_baidu_internal(href):
                    continue
                body = _join_text(
                    item.xpath(
                        ".//*[@data-module='abstract']//text()"
                        " | .//div[contains(@class, 'c-abstract')]//text()"
                        " | .//div[contains(@class, 'c-span-last')]//text()"
                    )
                )
                results.append({"title": title, "href": href, "body": body, "engine": self.ENGINE_NAME})
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
        search_url = self.SEARCH_URL.replace("{keyword}", encoded_query)
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
                    title = "".join(title_elems).strip()
                    href = "".join(href_elems).strip()
                    body = "".join(body_elems).strip() if body_elems else ""

                    if title and href:
                        results.append({"title": title, "href": href, "body": body, "engine": self.ENGINE_NAME})
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

    def __init__(self, proxy: str | None = None):
        """初始化 Google 搜索引擎并附加浏览器风格请求头。"""
        super().__init__(proxy)
        # 添加更多请求头以模拟浏览器
        self.session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def build_search_url(self, query: str, **kwargs) -> str:
        """构建搜索 URL"""
        encoded_query = quote(query)
        search_url = self.SEARCH_URL.replace("{keyword}", encoded_query)
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
                body_elems = item.xpath(
                    ".//div[contains(@class, 'IsZvec')]//text() | .//div[contains(@class, 'VwiK3b')]//text()"
                )

                if title_elems and href_elems:
                    title = "".join(title_elems).strip()
                    href = "".join(href_elems).strip()

                    # 过滤无效的 href
                    if not href or not href.startswith("http"):
                        continue

                    body = "".join(body_elems).strip() if body_elems else ""

                    if title and href:
                        results.append({"title": title, "href": href, "body": body, "engine": self.ENGINE_NAME})
            except Exception as e:
                logger.debug("解析搜索条目失败: %s", e)
                continue

        return results


_RELATIVE_AGE = re.compile(r"(\d+)\s*(分钟|小时|天|周|个月|月|年)前")
_ABSOLUTE_AGE = re.compile(r"(20\d\d)-(\d{1,2})-(\d{1,2})")
_AGE_UNIT_DAYS = {"分钟": 1 / 1440, "小时": 1 / 24, "天": 1.0, "周": 7.0, "个月": 30.0, "月": 30.0, "年": 365.0}


def _age_in_days(text: str, now: float) -> float | None:
    """把 360 的时间标注换算成天数。

    360 同时使用两种写法：相对值（``1天前``）和绝对值（``2026-09-18 21:49``），
    解析不出来时返回 None，调用方据此丢弃该条，而不是假装它满足时间范围。
    """
    match = _RELATIVE_AGE.search(text)
    if match:
        return float(match.group(1)) * _AGE_UNIT_DAYS[match.group(2)]
    match = _ABSOLUTE_AGE.search(text)
    if match:
        try:
            published = time.mktime(
                (int(match.group(1)), int(match.group(2)), int(match.group(3)), 0, 0, 0, 0, 0, -1)
            )
        except (OverflowError, ValueError):
            return None
        return max(0.0, (now - published) / 86400)
    return None


def _is_360_internal(url: str) -> bool:
    """判断是否 360 自家地址（AI 摘要卡、影视垂直、快看号等），这类不是可用证据。"""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return True
    hostname = (parsed.hostname or "").lower().rstrip(".")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ("so.com", "360.cn", "360kuai.com", "360kan.com", "360doc.com")
    )


def _so360_within_window(item: html.HtmlElement, days: int, now: float) -> bool:
    """按条目自带的时间戳校验是否落在请求的时间范围内。"""
    stamps = item.xpath(
        ".//span[contains(@class, 'time')]/text() | .//span[contains(@class, 'g-c-gray')]/text()"
    )
    for stamp in stamps:
        age = _age_in_days(stamp, now)
        if age is not None:
            return age <= days
    return False


class So360SearchNoApi(BaseNoApiKeySearchEngine):
    """360 搜索 (无需 API Key)

    百度被反爬拦截时的首选降级源：中文分词比 Bing 中国好得多，同一个
    ``宁德时代 储能产业链`` 能返回储能产业链拆解文章，而 Bing 只给得出「宁德市」百科。

    限定时间范围时切到 news 子站并按发布时间倒序；那里每条都带可解析的时间戳，
    因此能真正校验时效。通用站只有零散日期、校验不了，就不参与限定时间的降级。
    """

    ENGINE_NAME = "so360"
    ENGINE_DISPLAY_NAME = "360 搜索"
    WEB_SEARCH_URL = "https://www.so.com/s?q={keyword}"
    NEWS_SEARCH_URL = "https://news.so.com/ns?q={keyword}&rank=pdate"
    REQUIRES_PROXY = False
    # parse_results 可能被单独调用（测试、复用），因此要有默认值而不是只在 search 里赋值。
    _time_range = "any"

    def build_search_url(self, query: str, **kwargs) -> str:
        """构建搜索 URL；限定时间时改用按发布时间排序的新闻入口。"""
        template = self.WEB_SEARCH_URL
        if _TIME_RANGE_DAYS.get(kwargs.get("time_range", "any")) is not None:
            template = self.NEWS_SEARCH_URL
        return template.replace("{keyword}", quote(query))

    def search(self, query: str, max_results: int = 10, timeout: int = 15, **kwargs) -> List[Dict[str, Any]]:
        """执行搜索；把时间范围留给解析器校验条目时效。"""
        self._time_range = kwargs.get("time_range", "any")
        try:
            return super().search(query, max_results=max_results, timeout=timeout, **kwargs)
        finally:
            self._time_range = "any"

    def parse_results(self, tree: html.HtmlElement) -> List[Dict[str, Any]]:
        """解析 HTML 搜索结果"""
        results = []
        days = _TIME_RANGE_DAYS.get(self._time_range)
        now = time.time()
        for item in tree.xpath("//li[contains(@class, 'res-list')]"):
            try:
                # 两种版式的链接层级相反：通用站是 h3 > a，news 子站是 a > h3。
                anchor = item.xpath(".//h3//a[@href] | .//a[@href][h3]")
                if not anchor:
                    continue
                link = anchor[0]
                # news 子站把真实地址放在 li 的 data-url 上，通用站放在 a 的 data-mdurl 上；
                # 两者都取不到时只剩 so.com 跳转 token，对用户没有价值。
                href = (item.get("data-url") or link.get("data-mdurl") or "").strip()
                if not href.startswith(("http://", "https://")) or _is_360_internal(href):
                    continue
                title = (link.get("title") or "").strip() or _join_text(link.itertext())
                if not title:
                    continue
                if days is not None and not _so360_within_window(item, days, now):
                    continue
                body = _join_text(
                    item.xpath(
                        ".//p[contains(@class, 'summary')]//text()"
                        " | .//p[contains(@class, 'res-desc')]//text()"
                    )
                )
                results.append({"title": title, "href": href, "body": body, "engine": self.ENGINE_NAME})
            except Exception as e:
                logger.debug("解析 360 搜索条目失败: %s", e)
                continue
        return results


class WebSearchProvider:
    """Stateless registry entry; each attempt owns its HTTP session."""

    def __init__(self, name: str, engine_class: type[BaseNoApiKeySearchEngine]) -> None:
        self.name = name
        self._engine_class = engine_class

    def search(
        self,
        query: str,
        max_results: int = 10,
        timeout: int = 15,
        *,
        time_range: str = "any",
        language: str = "zh",
    ) -> list[dict[str, Any]]:
        engine = self._engine_class()
        try:
            return engine.search(
                query,
                max_results=max_results,
                timeout=timeout,
                time_range=time_range,
                language=language,
            )
        finally:
            engine.session.close()


# Search traffic must not share the stock-data provider's circuit or metrics.
baidu_search_provider = WebSearchProvider("baidu_search", BaiduSearchNoApi)
bing_cn_search_provider = WebSearchProvider("bing_cn_search", BingCnSearchNoAPI)
so360_search_provider = WebSearchProvider("so360_search", So360SearchNoApi)
google_search_provider = WebSearchProvider("google_search", GoogleSearchNoAPI)
