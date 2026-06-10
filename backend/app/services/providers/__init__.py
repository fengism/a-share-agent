from __future__ import annotations

from importlib import import_module

_CLASS_EXPORTS = {
    "AkshareDataProvider": "app.services.providers.akshare",
    "BaiduDataProvider": "app.services.providers.baidu",
    "ClsDataProvider": "app.services.providers.cls",
    "EastMoneyDataProvider": "app.services.providers.eastmoney",
    "IwencaiDataProvider": "app.services.providers.iwencai",
    "RssDataProvider": "app.services.providers.rss",
    "SinaDataProvider": "app.services.providers.sina",
    "TdxDataProvider": "app.services.providers.tdx",
    "TencentDataProvider": "app.services.providers.tencent",
    "ThsDataProvider": "app.services.providers.ths",
    "TwitterDataProvider": "app.services.providers.twitter",
}

_INSTANCE_EXPORTS = {
    "akshare": ("app.services.providers.akshare", "akshare_provider"),
    "baidu": ("app.services.providers.baidu", "baidu_provider"),
    "cls": ("app.services.providers.cls", "cls_provider"),
    "eastmoney": ("app.services.providers.eastmoney", "eastmoney_provider"),
    "iwencai": ("app.services.providers.iwencai", "iwencai_provider"),
    "rss": ("app.services.providers.rss", "rss_provider"),
    "sina": ("app.services.providers.sina", "sina_provider"),
    "tdx": ("app.services.providers.tdx", "tdx_provider"),
    "tencent": ("app.services.providers.tencent", "tencent_provider"),
    "ths": ("app.services.providers.ths", "ths_provider"),
    "twitter": ("app.services.providers.twitter", "twitter_provider"),
}

__all__ = list(_CLASS_EXPORTS)


def __getattr__(name: str):
    """按需加载 provider class，避免导入包时触发全部 provider 模块初始化。"""
    module_name = _CLASS_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """让 dir() 暴露懒加载的 provider class 名称。"""
    return sorted(list(globals().keys()) + __all__)


def get_provider(name: str):
    """按名称获取 provider 单例，只有真正使用时才导入对应模块。"""
    module_name, attr_name = _INSTANCE_EXPORTS[name]
    module = import_module(module_name)
    return getattr(module, attr_name)
