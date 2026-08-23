import json
import logging
from typing import cast

from app.configuration.paths import DATA_DIR
from app.core.cache import cache, dated_cache_key
from app.core.concurrency.rate_limiter import call_blocking
from app.core.concurrency.singleflight import SyncSingleFlight
from app.financial_data.stock.classification import builder as industry_builder
from app.financial_data.stock.classification import repository as industry_store
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_INDUSTRY_LEVEL_NAMES = {1: "一级", 2: "二级"}
_INDUSTRY_MAPPING_FILES = {
    1: DATA_DIR / "industry_first_mapping.json",
    2: DATA_DIR / "industry_second_mapping.json",
}
_INDUSTRY_FILE_CACHE_KEYS = {
    1: ("industry_first_mapping_file", "industry_first_list_file"),
    2: ("industry_second_mapping_file", "industry_second_list_file"),
}
_INDUSTRY_MAPPING_FILE = _INDUSTRY_MAPPING_FILES[2]
_INDUSTRY_MAPPING_CACHE_KEY, _INDUSTRY_LIST_CACHE_KEY = _INDUSTRY_FILE_CACHE_KEYS[2]
_INDUSTRY_MAPPING_TTL = 24 * 60 * 60
_MIN_VALID_MAPPING_SIZE = 4000
_sina_mapping_singleflight: SyncSingleFlight[dict[int, tuple[dict[str, str], list[str]]]] = SyncSingleFlight()


def _validate_level(level: int) -> None:
    if level not in _INDUSTRY_LEVEL_NAMES:
        raise ValueError(f"不支持的申万行业级别: {level}")


def _get_akshare_provider():
    return get_provider("akshare")


def _get_sina_provider():
    return get_provider("sina")


def _is_valid_mapping(mapping: dict[str, str]) -> bool:
    return len(mapping) > _MIN_VALID_MAPPING_SIZE


def _build_industry_list(mapping: dict[str, str]) -> list[str]:
    return cast(list[str], industry_store.build_industry_list(mapping))


def _load_mapping_file(level: int = 2) -> dict[str, str]:
    _validate_level(level)
    return cast(dict[str, str], industry_store.load_mapping_file(_INDUSTRY_MAPPING_FILES[level]))


def _get_cached_pair(mapping_key: str, list_key: str) -> tuple[dict[str, str], list[str]] | None:
    return cast(
        tuple[dict[str, str], list[str]] | None,
        industry_store.get_cached_pair(cache, mapping_key, list_key),
    )


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


def _cache_industry_mapping(
    mapping: dict[str, str],
    industry_list: list[str],
    level: int = 2,
) -> None:
    _validate_level(level)
    mapping_key, list_key = _INDUSTRY_FILE_CACHE_KEYS[level]
    _cache_pair(mapping_key, list_key, mapping, industry_list)


def _built_cache_keys(level: int = 2) -> tuple[str, str]:
    _validate_level(level)
    label = _INDUSTRY_LEVEL_NAMES[level]
    return dated_cache_key(f"industry_sw_{level}_mapping"), dated_cache_key(f"industry_sw_{label}_list")


def _cache_built_mapping(
    mapping: dict[str, str],
    industry_list: list[str],
    level: int = 2,
) -> None:
    mapping_key, list_key = _built_cache_keys(level)
    _cache_pair(mapping_key, list_key, mapping, industry_list)


def _pick_first_column(columns: list[str], candidates: list[str]) -> str | None:
    return cast(str | None, industry_builder.pick_first_column(columns, candidates))


def _normalize_sw_industry_name(value: object) -> str | None:
    return cast(str | None, industry_builder.normalize_sw_industry_name(value))


def _load_sw_components(industry_code: str):
    return provider_gateway.call_sync(
        "akshare",
        "sw_index_components",
        lambda: _get_akshare_provider().fetch_sw_index_components(symbol=industry_code),
        max_attempts=1,
        retry_budget_seconds=5.0,
    )


def _build_industry_mapping_sw_index_akshare(level: int) -> tuple[dict[str, str], list[str]]:
    _validate_level(level)
    provider = _get_akshare_provider()
    index_dataframe = provider_gateway.call_sync(
        "akshare",
        "sw_index_realtime" if level == 2 else "sw_index_realtime_level_1",
        lambda: provider.fetch_sw_index_realtime() if level == 2 else provider.fetch_sw_index_realtime(level=level),
        max_attempts=1,
        retry_budget_seconds=8.0,
    )
    return cast(
        tuple[dict[str, str], list[str]],
        industry_builder.build_akshare_mapping(
            index_dataframe,
            _load_sw_components,
            logger,
            _pick_first_column,
            _normalize_sw_industry_name,
        ),
    )


def _load_industry_mappings_sina() -> dict[int, tuple[dict[str, str], list[str]]]:
    return cast(
        dict[int, tuple[dict[str, str], list[str]]],
        provider_gateway.call_sync(
            "sina",
            "sw_industry_mappings",
            lambda: _get_sina_provider().fetch_sw_industry_mappings(),
            max_attempts=1,
            retry_budget_seconds=30.0,
        ),
    )


def _build_industry_mappings_sina() -> dict[int, tuple[dict[str, str], list[str]]]:
    return cast(
        dict[int, tuple[dict[str, str], list[str]]],
        _sina_mapping_singleflight.do("sina_sw_industry_mappings", _load_industry_mappings_sina),
    )


def _build_industry_mapping_sw_level(level: int) -> tuple[dict[str, str], list[str]]:
    _validate_level(level)
    mapping_key, list_key = _built_cache_keys(level)
    cached = _get_cached_pair(mapping_key, list_key)
    if cached is not None:
        return cached

    try:
        sina_mappings = _build_industry_mappings_sina()
        for result_level, pair in sina_mappings.items():
            if result_level not in _INDUSTRY_LEVEL_NAMES:
                continue
            result_mapping, result_list = pair
            if _is_valid_mapping(result_mapping):
                _cache_built_mapping(result_mapping, result_list, result_level)
        mapping, industry_list = sina_mappings.get(level, ({}, []))
        if _is_valid_mapping(mapping):
            logger.info(
                "申万%s级行业映射采用新浪数据: stocks=%s industries=%s",
                _INDUSTRY_LEVEL_NAMES[level],
                len(mapping),
                len(industry_list),
            )
            return mapping, industry_list
        logger.info("新浪申万%s级行业映射数据量不足: count=%s", _INDUSTRY_LEVEL_NAMES[level], len(mapping))
    except Exception as exc:
        logger.info("新浪申万%s级行业映射不可用: %s", _INDUSTRY_LEVEL_NAMES[level], exc)

    try:
        mapping, industry_list = _build_industry_mapping_sw_index_akshare(level)
        if _is_valid_mapping(mapping):
            _cache_built_mapping(mapping, industry_list, level)
            logger.info(
                "申万%s级行业映射采用 AKShare 备用数据: stocks=%s industries=%s",
                _INDUSTRY_LEVEL_NAMES[level],
                len(mapping),
                len(industry_list),
            )
            return mapping, industry_list
        logger.info("AKShare 申万%s级行业映射数据量不足: count=%s", _INDUSTRY_LEVEL_NAMES[level], len(mapping))
    except Exception as exc:
        logger.info("AKShare 申万%s级行业映射不可用: %s", _INDUSTRY_LEVEL_NAMES[level], exc)

    logger.info("申万%s级行业刷新失败，保留现有本地快照", _INDUSTRY_LEVEL_NAMES[level])
    return {}, []


def _build_industry_mapping_sw_second() -> tuple[dict[str, str], list[str]]:
    """Compatibility wrapper for callers that consume level-two industries."""
    return _build_industry_mapping_sw_level(2)


def update_industry_mapping_sw_level_file(level: int) -> tuple[dict[str, str], list[str]]:
    """Rebuild one Shenwan level and atomically replace only a complete snapshot."""
    _validate_level(level)
    mapping, industry_list = _build_industry_mapping_sw_level(level)
    if not _is_valid_mapping(mapping):
        return mapping, industry_list

    industry_store.write_mapping_file(_INDUSTRY_MAPPING_FILES[level], mapping)
    _cache_industry_mapping(mapping, industry_list, level)
    return mapping, industry_list


def update_industry_mapping_sw_files() -> dict[int, tuple[dict[str, str], list[str]]]:
    """Refresh level-one and level-two snapshots independently."""
    return {level: update_industry_mapping_sw_level_file(level) for level in (1, 2)}


def fetch_industry_mapping_sw_level(level: int) -> tuple[dict[str, str], list[str]]:
    """Load one Shenwan level from cache/local snapshot, rebuilding when unavailable."""
    _validate_level(level)
    mapping_key, list_key = _INDUSTRY_FILE_CACHE_KEYS[level]
    cached = _get_cached_pair(mapping_key, list_key)
    if cached is not None:
        return cached

    path = _INDUSTRY_MAPPING_FILES[level]
    try:
        mapping = _load_mapping_file(level)
        if not _is_valid_mapping(mapping):
            raise ValueError(f"行业映射数据量不足: {len(mapping)}")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("行业映射文件不可用，尝试重新生成: path=%s, error=%s", path, exc)
        mapping, industry_list = update_industry_mapping_sw_level_file(level)
    else:
        industry_list = _build_industry_list(mapping)

    _cache_industry_mapping(mapping, industry_list, level)
    return mapping, industry_list


def fetch_industry_mapping_sw_first() -> tuple[dict[str, str], list[str]]:
    return fetch_industry_mapping_sw_level(1)


def fetch_industry_mapping_sw_second() -> tuple[dict[str, str], list[str]]:
    """同步获取申万二级行业映射，优先使用缓存与本地文件。"""
    return fetch_industry_mapping_sw_level(2)


def update_industry_mapping_sw_second_file() -> tuple[dict[str, str], list[str]]:
    """Refresh both levels while preserving the established level-two return contract."""
    return update_industry_mapping_sw_files()[2]


async def build_industry_mapping() -> tuple[dict[str, str], list[str]]:
    return cast(
        tuple[dict[str, str], list[str]],
        await call_blocking(fetch_industry_mapping_sw_second),
    )


async def get_industry_mapping(level: int = 2) -> dict[str, str]:
    mapping, _ = cast(
        tuple[dict[str, str], list[str]],
        await call_blocking(fetch_industry_mapping_sw_level, level),
    )
    return mapping


async def get_industry_list(level: int = 2) -> list[str]:
    _, industry_list = cast(
        tuple[dict[str, str], list[str]],
        await call_blocking(fetch_industry_mapping_sw_level, level),
    )
    return industry_list
