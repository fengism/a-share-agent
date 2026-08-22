import json
from pathlib import Path

from app.infrastructure.persistence.json_storage import atomic_write_text


def build_industry_list(mapping: dict[str, str]) -> list[str]:
    return sorted(set(mapping.values()))


def load_mapping_file(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as file:
        mapping = json.load(file)
    if not isinstance(mapping, dict):
        raise ValueError("行业映射文件格式异常")
    return {str(code): str(industry) for code, industry in mapping.items()}


def write_mapping_file(path: Path, mapping: dict[str, str]) -> None:
    atomic_write_text(
        path,
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True),
    )


def get_cached_pair(cache, mapping_key: str, list_key: str) -> tuple[dict[str, str], list[str]] | None:
    cached_mapping = cache.get(mapping_key)
    cached_industry_list = cache.get(list_key)
    if cached_mapping is not None and cached_industry_list is not None:
        return cached_mapping, cached_industry_list
    return None


def cache_pair(
    cache,
    mapping_key: str,
    list_key: str,
    mapping: dict[str, str],
    industry_list: list[str],
    ttl: int,
) -> None:
    cache.set(mapping_key, mapping, ttl=ttl)
    cache.set(list_key, industry_list, ttl=ttl)
