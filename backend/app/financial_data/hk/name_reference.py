"""港股名称识别：复用在 A 股上验证过的自动派生与语境门控。

数据来自 ``data/hk_stock_search_index.json``（code / name / english_name）。
完整名（长度 >= 3）高置信；派生简称与 2 字名需要同时出现股票语境词。
"""

from __future__ import annotations

import json
import logging

from app.configuration.paths import DATA_DIR
from app.financial_data.stock.profile.short_names import (
    build_pinyin_index,
    build_short_name_index,
    extract_pinyin_tokens,
    has_stock_context,
    is_generic_word,
    normalize_name,
)

logger = logging.getLogger(__name__)

_HK_NAME_FILE = DATA_DIR / "hk_stock_search_index.json"

# 2-3 字港股名与常见词/地名冲突，不参与识别。
_AMBIGUOUS_HK_NAMES: frozenset[str] = frozenset({
    "天安", "太古", "恒基", "银河", "远东", "航天", "电能", "新世界", "九龙", "长和",
})

_hk_source_key: tuple[int, int] | None = None
_hk_loaded = False
_hk_name_index: frozenset[str] = frozenset()
_hk_short_name_index: frozenset[str] = frozenset()
_hk_pinyin_index: frozenset[str] | None = None
_hk_names: tuple[str, ...] = ()


def build_hk_name_index(names: tuple[str, ...] | list[str]) -> frozenset[str]:
    """港股完整名高置信索引（长度 >= 3，排除歧义词）。"""
    return frozenset(
        name
        for raw in names
        if len(name := normalize_name(raw)) >= 3 and name not in _AMBIGUOUS_HK_NAMES
    )


def build_hk_short_name_index(names: tuple[str, ...] | list[str]) -> frozenset[str]:
    """港股派生简称：自动词缀 + 2 字品牌名，排除歧义词与通用词。"""
    normalized = [normalize_name(raw) for raw in names]
    aliases = set(build_short_name_index(normalized, include_exceptions=False))
    for name in normalized:
        if (
            len(name) == 2
            and name not in _AMBIGUOUS_HK_NAMES
            and not is_generic_word(name)
        ):
            aliases.add(name)
    return frozenset(aliases - _AMBIGUOUS_HK_NAMES)


def _read_hk_names() -> tuple[str, ...]:
    try:
        payload = json.loads(_HK_NAME_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("读取港股名称索引失败: %s", exc)
        return ()
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return ()
    return tuple(
        str(item["name"])
        for item in items
        if isinstance(item, dict) and item.get("name")
    )


def _ensure_hk_reference_indexes() -> None:
    global _hk_source_key, _hk_loaded, _hk_name_index, _hk_short_name_index, _hk_pinyin_index, _hk_names
    try:
        stat = _HK_NAME_FILE.stat()
        key: tuple[int, int] | None = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        key = None
    if _hk_loaded and key == _hk_source_key:
        return
    _hk_source_key = key
    _hk_loaded = True
    _hk_names = _read_hk_names() if key is not None else ()
    _hk_name_index = build_hk_name_index(_hk_names)
    _hk_short_name_index = build_hk_short_name_index(_hk_names)
    _hk_pinyin_index = None


def _ensure_hk_pinyin_index() -> frozenset[str]:
    global _hk_pinyin_index
    if _hk_pinyin_index is None:
        _ensure_hk_reference_indexes()
        _hk_pinyin_index = build_pinyin_index(_hk_names)
    return _hk_pinyin_index


def contains_hk_stock_name(message: str) -> bool:
    """港股完整名或拼音首字母（高置信）。"""
    _ensure_hk_reference_indexes()
    normalized = normalize_name(message)
    if len(normalized) >= 3 and _hk_name_index:
        if any(name in normalized for name in _hk_name_index):
            return True
    tokens = extract_pinyin_tokens(message)
    if not tokens:
        return False
    index = _ensure_hk_pinyin_index()
    return any(token in index for token in tokens)


def contains_hk_short_stock_name(message: str) -> bool:
    """港股派生简称（不含语境门控）。"""
    normalized = normalize_name(message)
    if len(normalized) < 2:
        return False
    _ensure_hk_reference_indexes()
    return any(alias in normalized for alias in _hk_short_name_index)


def mentions_hk_stock_target(message: str) -> bool:
    """是否应视为港股标的：高置信，或“简称 + 股票语境词”。"""
    if contains_hk_stock_name(message):
        return True
    if not has_stock_context(message):
        return False
    return contains_hk_short_stock_name(message)


__all__ = [
    "build_hk_name_index",
    "build_hk_short_name_index",
    "contains_hk_short_stock_name",
    "contains_hk_stock_name",
    "mentions_hk_stock_target",
]
