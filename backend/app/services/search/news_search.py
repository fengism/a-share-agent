
from app.models.search_item import NewsSearchItem
from app.services.providers.akshare import akshare_provider as _akshare_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.news_utils import dedupe_news_items, news_sort_key


async def search_market_news(query: str="") -> list[NewsSearchItem]:
    text = query.strip()
    cache_key = dated_cache_key("market_news_search", text)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = await call_blocking(_akshare_provider.fetch_stock_news, code=text)
    result = dedupe_news_items(result)
    result.sort(key=news_sort_key, reverse=True)
    cache.set(cache_key, result, ttl=600)
    return result


def fetch_news_em(code: str = "", code_name: str = "") -> list[NewsSearchItem]:
    from app.services.providers.eastmoney import eastmoney_provider

    return eastmoney_provider.fetch_market_news(code=code, code_name=code_name)


def fetch_news_rss(code: str = "", code_name: str = "") -> list[NewsSearchItem]:
    from app.services.providers.rss import rss_provider
    return rss_provider.fetch_market_news(code=code, code_name=code_name)


def fetch_news_cls(code: str = "", code_name: str = "") -> list[NewsSearchItem]:
    from app.services.providers.cls import cls_provider
    return cls_provider.fetch_market_news(code=code, code_name=code_name)

def fetch_news_comment_em(code: str = "", code_name: str = "") -> list[NewsSearchItem]:
    from app.services.providers.eastmoney import eastmoney_provider

    return eastmoney_provider.fetch_stock_comments(code=code, code_name=code_name)


if __name__ == "__main__":
    results = fetch_news_em()
    print(results)
