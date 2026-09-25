from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal
from urllib.parse import urlsplit

from app.core.concurrency.rate_limiter import call_blocking, misc_semaphore
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

SearchEngineName = Literal["baidu", "bing_cn", "google"]
SearchTimeRange = Literal["day", "week", "month", "half_year", "any"]
SearchLanguage = Literal["zh", "any"]
DEFAULT_SEARCH_ENGINE: SearchEngineName = "bing_cn"
_BAIJIAHAO_HOST = "baijiahao.baidu.com"
_BAIJIAHAO_EXCLUSION = f"-site:{_BAIJIAHAO_HOST}"

_SEARCH_PROVIDERS = {
    "baidu": "baidu_search",
    "bing_cn": "bing_cn_search",
    "google": "google_search",
}


def _engine_query(query: str, engine: SearchEngineName) -> str:
    if engine != "baidu" or _BAIJIAHAO_EXCLUSION in query.lower():
        return query
    return f"{query} {_BAIJIAHAO_EXCLUSION}"


def _normalize_results(
    results: list[dict[str, Any]],
    engine: SearchEngineName,
    max_results: int,
    language: SearchLanguage,
) -> list[dict[str, str]]:
    normalized = []
    seen_urls = set()
    for item in results:
        title = str(item.get("title") or "").strip()
        url = str(item.get("href") or "").strip()
        try:
            parsed_url = urlsplit(url)
        except ValueError:
            continue
        scheme = parsed_url.scheme
        hostname = (parsed_url.hostname or "").lower().rstrip(".")
        if engine == "baidu" and (hostname == _BAIJIAHAO_HOST or hostname.endswith(f".{_BAIJIAHAO_HOST}")):
            continue
        if not title or scheme not in {"http", "https"} or url in seen_urls:
            continue
        seen_urls.add(url)
        normalized.append(
            {
                "title": title[:300],
                "url": url[:2048],
                "snippet": str(item.get("body") or "").strip()[:1000],
                "engine": str(item.get("engine") or engine)[:32],
            }
        )
    if language == "zh":
        normalized.sort(
            key=lambda item: not any("\u3400" <= char <= "\u9fff" for char in f"{item['title']} {item['snippet']}")
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
    semaphore=misc_semaphore,
) -> dict[str, Any]:
    try:
        provider_name = _SEARCH_PROVIDERS[engine]
    except KeyError as exc:
        raise ValueError(f"unsupported search engine: {engine}") from exc
    normalized_query = query.strip()
    results = await provider_gateway.call(
        provider_name,
        "search",
        lambda: call_blocking_func(
            get_provider(provider_name).search,
            _engine_query(normalized_query, engine),
            max_results=min(max_results * 2, 20),
            time_range=time_range,
            language=language,
            semaphore=semaphore,
        ),
    )
    normalized_results = _normalize_results(results, engine, max_results, language)
    return {
        "query": normalized_query,
        "engine": engine,
        "time_range": time_range,
        "language": language,
        "count": len(normalized_results),
        "results": normalized_results,
        "detail_hint": (
            "搜索结果仅包含标题和摘要；需要详细内容时，使用 web_fetch 抓取对应 URL，"
            "需要同时阅读多个结果时使用 fetch_urls。"
        ),
    }
