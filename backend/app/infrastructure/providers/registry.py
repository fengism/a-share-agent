from importlib import import_module

_PROVIDER_EXPORTS = {
    "akshare": ("app.infrastructure.providers.akshare.provider", "akshare_provider"),
    "baidu": ("app.infrastructure.providers.baidu.provider", "baidu_provider"),
    "cls": ("app.infrastructure.providers.cls", "cls_provider"),
    "eastmoney": ("app.infrastructure.providers.eastmoney", "eastmoney_provider"),
    "iwencai": ("app.infrastructure.providers.iwencai", "iwencai_provider"),
    "rss": ("app.infrastructure.providers.news", "news_provider"),
    "sina": ("app.infrastructure.providers.sina.provider", "sina_provider"),
    "tdx": ("app.infrastructure.providers.tdx", "tdx_provider"),
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
