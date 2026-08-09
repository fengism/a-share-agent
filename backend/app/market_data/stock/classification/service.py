import json
import logging

from app.configuration.paths import DATA_DIR
from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import call_blocking
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider
from app.market_data.stock.classification import builder as industry_builder
from app.market_data.stock.classification import repository as industry_store

logger = logging.getLogger(__name__)

_INDUSTRY_MAPPING_FILE = DATA_DIR / "industry_second_mapping.json"
_INDUSTRY_MAPPING_CACHE_KEY = "industry_second_mapping_file"
_INDUSTRY_LIST_CACHE_KEY = "industry_second_list_file"
_INDUSTRY_MAPPING_TTL = 24 * 60 * 60
_MIN_VALID_MAPPING_SIZE = 4000


def _get_akshare_provider():
    return get_provider("akshare")


def _get_eastmoney_provider():
    return get_provider("eastmoney")


def _is_valid_mapping(mapping: dict[str, str]) -> bool:
    return len(mapping) > _MIN_VALID_MAPPING_SIZE


def _build_industry_list(mapping: dict[str, str]) -> list[str]:
    return industry_store.build_industry_list(mapping)


def _load_mapping_file() -> dict[str, str]:
    return industry_store.load_mapping_file(_INDUSTRY_MAPPING_FILE)


def _get_cached_pair(mapping_key: str, list_key: str) -> tuple[dict[str, str], list[str]] | None:
    return industry_store.get_cached_pair(cache, mapping_key, list_key)


def _cache_pair(
    mapping_key: str,
    list_key: str,
    mapping: dict[str, str],
    industry_list: list[str],
) -> None:
    industry_store.cache_pair(
        cache,
        mapping_key,
        list_key,
        mapping,
        industry_list,
        _INDUSTRY_MAPPING_TTL,
    )


def _cache_industry_mapping(mapping: dict[str, str], industry_list: list[str]) -> None:
    _cache_pair(_INDUSTRY_MAPPING_CACHE_KEY, _INDUSTRY_LIST_CACHE_KEY, mapping, industry_list)


def _built_cache_keys() -> tuple[str, str]:
    return dated_cache_key("industry_second_mapping"), dated_cache_key("industry_second_list")


def _cache_built_mapping(mapping: dict[str, str], industry_list: list[str]) -> None:
    mapping_key, list_key = _built_cache_keys()
    _cache_pair(mapping_key, list_key, mapping, industry_list)


def _pick_first_column(columns: list[str], candidates: list[str]) -> str | None:
    return industry_builder.pick_first_column(columns, candidates)


def _normalize_sw_industry_name(value: object) -> str | None:
    return industry_builder.normalize_sw_industry_name(value)


def _load_sw_components(industry_code: str):
    return provider_gateway.call_sync(
        "akshare",
        "sw_index_components",
        lambda: _get_akshare_provider().fetch_sw_index_components(symbol=industry_code),
    )


def _build_industry_mapping_sw_second_index_akshare() -> tuple[dict[str, str], list[str]]:
    index_dataframe = provider_gateway.call_sync(
        "akshare",
        "sw_index_realtime",
        lambda: _get_akshare_provider().fetch_sw_index_realtime(),
    )
    return industry_builder.build_akshare_mapping(
        index_dataframe,
        _load_sw_components,
        logger,
        _pick_first_column,
        _normalize_sw_industry_name,
    )


def _build_industry_mapping_sw_second() -> tuple[dict[str, str], list[str]]:
    mapping_key, list_key = _built_cache_keys()
    cached = _get_cached_pair(mapping_key, list_key)
    if cached is not None:
        return cached

    try:
        mapping, industry_list = _build_industry_mapping_sw_second_index_akshare()
        if _is_valid_mapping(mapping):
            _cache_built_mapping(mapping, industry_list)
            return mapping, industry_list
        logger.info("申万二级行业列表数据量不足: count=%s", len(mapping))
    except Exception as exc:
        logger.info("申万二级行业列表不可用: %s", exc)

    try:
        mapping, industry_list = provider_gateway.call_sync(
            "eastmoney",
            "industry_mapping",
            lambda: _get_eastmoney_provider().build_industry_mapping(),
            is_fallback_attempt=True,
        )
        if _is_valid_mapping(mapping):
            _cache_built_mapping(mapping, industry_list)
            return mapping, industry_list
        logger.info("东方财富直连行业列表数据量不足: count=%s", len(mapping))
    except Exception as exc:
        logger.info("东方财富直连获取行业列表失败: %s", exc)

    return {}, []


def fetch_industry_mapping_sw_second() -> tuple[dict[str, str], list[str]]:
    """同步获取申万二级行业映射，优先使用缓存与本地文件。"""
    cached = _get_cached_pair(_INDUSTRY_MAPPING_CACHE_KEY, _INDUSTRY_LIST_CACHE_KEY)
    if cached is not None:
        return cached

    try:
        mapping = _load_mapping_file()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("行业映射文件不可用，尝试重新生成: path=%s, error=%s", _INDUSTRY_MAPPING_FILE, exc)
        mapping, industry_list = update_industry_mapping_sw_second_file()
    else:
        industry_list = _build_industry_list(mapping)

    _cache_industry_mapping(mapping, industry_list)
    return mapping, industry_list


def update_industry_mapping_sw_second_file() -> tuple[dict[str, str], list[str]]:
    """重新构建申万二级行业映射并写回本地文件。"""
    mapping, industry_list = _build_industry_mapping_sw_second()
    if not _is_valid_mapping(mapping):
        return mapping, industry_list

    industry_store.write_mapping_file(_INDUSTRY_MAPPING_FILE, mapping)
    _cache_industry_mapping(mapping, industry_list)
    return mapping, industry_list


async def build_industry_mapping() -> tuple[dict[str, str], list[str]]:
    return await call_blocking(fetch_industry_mapping_sw_second)


async def get_industry_mapping() -> dict[str, str]:
    mapping, _ = await call_blocking(fetch_industry_mapping_sw_second)
    return mapping


async def get_industry_list() -> list[str]:
    _, industry_list = await call_blocking(fetch_industry_mapping_sw_second)
    return industry_list
