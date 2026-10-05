from importlib import import_module

_PROVIDER_EXPORTS = {
    "akshare": ("app.infrastructure.providers.akshare.provider", "akshare_provider"),
    "anysearch": ("app.infrastructure.providers.anysearch", "anysearch_provider"),
    "baidu_search": ("app.infrastructure.providers.web_search", "baidu_search_provider"),
    "bing_cn_search": ("app.infrastructure.providers.web_search", "bing_cn_search_provider"),
    "baidu": ("app.infrastructure.providers.baidu.provider", "baidu_provider"),
    "cls": ("app.infrastructure.providers.cls", "cls_provider"),
    "cninfo": ("app.infrastructure.providers.cninfo", "cninfo_provider"),
    "eastmoney": ("app.infrastructure.providers.eastmoney", "eastmoney_provider"),
    "exchange": ("app.infrastructure.providers.exchange", "exchange_provider"),
    "fred": ("app.infrastructure.providers.fred", "fred_provider"),
    "fuyao": ("app.infrastructure.providers.fuyao", "fuyao_provider"),
    "google_search": ("app.infrastructure.providers.web_search", "google_search_provider"),
    "iwencai": ("app.infrastructure.providers.iwencai", "iwencai_provider"),
    "kaipanhong": ("app.infrastructure.providers.kaipanhong", "kaipanhong_provider"),
    "legulegu": ("app.infrastructure.providers.legulegu.provider", "legulegu_provider"),
    "nbs": ("app.infrastructure.providers.nbs", "nbs_provider"),
    "rss": ("app.infrastructure.providers.news", "news_provider"),
    "sge": ("app.infrastructure.providers.sge", "sge_provider"),
    "sina": ("app.infrastructure.providers.sina.provider", "sina_provider"),
    "sina_hk": ("app.infrastructure.providers.sina.hk", "sina_hk_provider"),
    "so360_search": ("app.infrastructure.providers.web_search", "so360_search_provider"),
    "tdxhub": ("app.infrastructure.providers.tdxhub", "tdxhub_provider"),
    "tencent": ("app.infrastructure.providers.tencent", "tencent_provider"),
    "ths": ("app.infrastructure.providers.ths.provider", "ths_provider"),
    "twitter": ("app.infrastructure.providers.twitter", "twitter_provider"),
}


def get_provider(name: str):
    """Return a lazily imported provider singleton by its stable short name."""
    try:
        module_name, attribute_name = _PROVIDER_EXPORTS[name]
    except KeyError as exc:
        raise ValueError(f"unknown provider: {name}") from exc
    module = import_module(module_name)
    return getattr(module, attribute_name)
