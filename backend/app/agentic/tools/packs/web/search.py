from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from app.core.cache import TTLCache
from app.core.cache_policies import AGENT_WEB_SEARCH
from app.core.concurrency.rate_limiter import call_blocking, search_semaphore
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

SEARCH_CACHE_TTL = AGENT_WEB_SEARCH.ttl_seconds
search_cache = TTLCache(maxsize=128, name="agent_web_search")

SearchEngineName = Literal["baidu", "so360", "bing_cn", "google"]
SearchTimeRange = Literal["day", "week", "month", "half_year", "any"]
SearchLanguage = Literal["zh", "any"]
DEFAULT_SEARCH_ENGINE: SearchEngineName = "baidu"
_BAIJIAHAO_HOST = "baijiahao.baidu.com"
_BAIJIAHAO_EXCLUSION = f"-site:{_BAIJIAHAO_HOST}"
# 保留 RFC 3986 的保留字与分隔符，只把裸中文/空格转成 %XX，已有转义不会被二次编码。
_URL_SAFE = "!#$%&'()*+,-./:;=?@_~[]"
# 已经是合法 ASCII URL 时直接跳过编码（不含空格与控制字符）。
_ASCII_URL_RE = re.compile(r"[\x21-\x7e]+")
# 渠道与会话标记，去重时忽略。刻意保守：id/page/docid 这类承载内容身份的不在其中。
_TRACKING_QUERY_KEYS = frozenset(
    {
        "app",
        "from",
        "for",
        "path",
        "redirect_pc",
        "ref",
        "share_source",
        "share_token",
        "sid",
        "src",
        "spm",
        "wfr",
    }
)
_TRACKING_QUERY_PREFIXES = ("utm_", "spm_")

_SEARCH_PROVIDERS = {
    "baidu": "baidu_search",
    "so360": "so360_search",
    "bing_cn": "bing_cn_search",
    "google": "google_search",
}
# 百度会按 IP + 指纹拦机器人，命中安全验证时返回空页面。降级顺序按中文相关性排：
# 360 分词明显优于 Bing（同一个「宁德时代 储能产业链」，Bing 只给得出「宁德市」百科）。
# Google 需要代理，不作为降级目标。
_FALLBACK_ENGINES: dict[str, tuple[SearchEngineName, ...]] = {
    "baidu": ("so360", "bing_cn"),
}


def _engine_query(query: str, engine: SearchEngineName) -> str:
    if engine != "baidu" or _BAIJIAHAO_EXCLUSION in query.lower():
        return query
    return f"{query} {_BAIJIAHAO_EXCLUSION}"


def _encode_url(url: str) -> str:
    """把 URL 里的裸中文/空格转成百分号编码。

    部分站点返回未编码的中文路径，浏览器只能按 UTF-8 猜测转义后展示，
    界面上就成了一串看不懂的 %E8%B4%B5...；这里在出库时统一成可直接展示的编码形式。

    快速路径只放行“可打印 ASCII 且不含空格”：``str.isascii()`` 对空格也成立，
    早先用它做判断会让含空格的 URL 原样漏出去，而空格在 URL 里本身就是非法字符。
    """
    if _ASCII_URL_RE.fullmatch(url):
        return url
    return quote(url, safe=_URL_SAFE)


def _url_identity(url: str) -> str:
    """按站点 + 路径 + 查询串归一后去重，忽略协议、www. 前缀、锚点与末尾斜杠。

    查询串里还要剔掉跟踪参数：腾讯新闻会把同一篇文章同时给出
    ``…/a/20260920A05HGF00`` 和 ``…/a/20260920A05HGF00?path=a&app=news&redirect_pc=1``，
    不剔除就会被当成两篇，白占一个结果名额。
    """
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".").removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query = urlencode(sorted(kept))
    return f"{host}{path}?{query}"


def _is_tracking_param(key: str) -> bool:
    """判断查询参数是否只是渠道/会话标记，不参与区分文章。

    刻意保守：只列确定的跟踪参数。``id``、``page``、``docid`` 这类承载内容身份的一律保留，
    误剔会把两篇不同文章合并成一条。
    """
    lowered = key.lower()
    return lowered in _TRACKING_QUERY_KEYS or lowered.startswith(_TRACKING_QUERY_PREFIXES)


def _title_identity(title: str) -> str:
    """标题归一：去掉标点空白后小写，用于识别同一篇稿件的转载版。"""
    return re.sub(r"[\W_]+", "", title).lower()


def _normalize_results(
    results: list[dict[str, Any]],
    engine: SearchEngineName,
    max_results: int,
) -> list[dict[str, str]]:
    """清洗并去重搜索结果。

    只保留外部 http(s) 地址，并按 URL 身份与标题各去重一次：新闻稿常被多个门户原样转载，
    标题完全一致基本可判定为同一篇，转载版对 Agent 没有额外信息量。

    这里刻意不做「中文优先」排序：Baidu / 360 / Bing 的结果标题全部含中文，稳定排序后
    顺序与原序完全一致，是一段无效代码；真正需要它的是英文引擎，而那些结果本来就该按
    相关性排，而不是按是否含中文字符。
    """
    normalized = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for item in results:
        title = " ".join(str(item.get("title") or "").split())
        url = _encode_url(str(item.get("href") or "").strip())
        try:
            parsed_url = urlsplit(url)
        except ValueError:
            continue
        scheme = parsed_url.scheme
        hostname = (parsed_url.hostname or "").lower().rstrip(".")
        if engine == "baidu" and (hostname == _BAIJIAHAO_HOST or hostname.endswith(f".{_BAIJIAHAO_HOST}")):
            continue
        if not title or scheme not in {"http", "https"} or not parsed_url.netloc:
            continue
        identity = _url_identity(url)
        title_identity = _title_identity(title)
        if identity in seen_urls or title_identity in seen_titles:
            continue
        seen_urls.add(identity)
        seen_titles.add(title_identity)
        normalized.append(
            {
                "title": title[:300],
                "url": url[:2048],
                "snippet": " ".join(str(item.get("body") or "").split())[:1000],
                "engine": str(item.get("engine") or engine)[:32],
            }
        )
    return normalized[:max_results]


async def execute_web_search(
    query: str,
    engine: SearchEngineName = DEFAULT_SEARCH_ENGINE,
    max_results: int = 5,
    time_range: SearchTimeRange = "half_year",
    language: SearchLanguage = "zh",
    *,
    call_blocking_func: Callable[..., Awaitable] = call_blocking,
    semaphore=search_semaphore,
    cache: TTLCache = search_cache,
) -> dict[str, Any]:
    if engine not in _SEARCH_PROVIDERS:
        raise ValueError(f"unsupported search engine: {engine}")
    normalized_query = query.strip()
    # 缓存整份出参：engine_used 也在里面，所以命中缓存时前端显示的数据源依旧正确。
    cache_key = f"search:{engine}:{max_results}:{time_range}:{language}:{normalized_query}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cast(dict[str, Any], cached)
    fetch_limit = min(max_results * 2, 20)
    engine_used = engine
    results: list[dict[str, Any]] = []
    raised: list[BaseException] = []
    answered = False
    for candidate in (engine, *_FALLBACK_ENGINES.get(engine, ())):
        try:
            results = await provider_gateway.call(
                _SEARCH_PROVIDERS[candidate],
                "search",
                lambda candidate=candidate: call_blocking_func(
                    get_provider(_SEARCH_PROVIDERS[candidate]).search,
                    _engine_query(normalized_query, candidate),
                    max_results=fetch_limit,
                    time_range=time_range,
                    language=language,
                    semaphore=semaphore,
                ),
                is_fallback_attempt=candidate != engine,
            )
        except Exception as error:  # noqa: BLE001 — 一个引擎抛异常不该掐断整条降级链
            raised.append(error)
            logger.warning("搜索引擎调用异常，降级重试 engine=%s: %s", candidate, error)
            results = []
            continue
        # 空结果与异常要分开记：引擎正常回了 0 条是事实，抛异常才是故障。
        answered = True
        if results:
            engine_used = candidate
            break
        logger.info("搜索引擎无结果，降级重试 engine=%s", candidate)
    if raised and not answered:
        # 所有引擎都抛异常：必须以错误收场。静默返回 count:0 会让「上游挂了」
        # 看起来像「确实没有相关结果」，模型就不会改用别的来源了。
        raise raised[-1]
    normalized_results = _normalize_results(results, engine_used, max_results)
    payload = {
        "query": normalized_query,
        "engine": engine_used,
        "time_range": time_range,
        "language": language,
        "count": len(normalized_results),
        "results": normalized_results,
        "detail_hint": (
            "搜索结果仅包含标题和摘要；需要详细内容时，使用 web_fetch 抓取对应 URL，"
            "需要同时阅读多个结果时使用 fetch_urls。"
        ),
    }
    # 空结果不缓存：那是引擎故障而非事实，缓存下来会把一次抖动放大成持续故障。
    if normalized_results:
        cache.set(cache_key, payload, SEARCH_CACHE_TTL)
    return payload
