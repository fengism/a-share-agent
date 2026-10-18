"""热门题材/行业映射与题材加分。"""

from __future__ import annotations

import asyncio
import logging
import math

from app.financial_data.market.public import (
    get_concept_constituents,
    get_ths_hot_concept,
    get_ths_hot_industry,
)
from app.modules.potential.common import _float_or_none
from app.modules.potential.constants import (
    _THEME_CONCEPT_LIMIT,
    _THEME_INDUSTRY_LIMIT,
    _THEME_STRENGTH_CAP,
)

logger = logging.getLogger(__name__)


def _theme_score(strength: float | None) -> float:
    """把题材强度映射为最终评分加成（最高 0.6）。"""
    if strength is None or not math.isfinite(strength) or strength <= 0:
        return 0.0
    return round(min(_THEME_STRENGTH_CAP, strength * _THEME_STRENGTH_CAP), 2)

def _constituent_codes(payload) -> set[str]:
    if isinstance(payload, dict):
        items = payload.get("items") or []
        return {str(item.get("code") or "") for item in items if isinstance(item, dict)}
    items = getattr(payload, "items", None) or []
    return {str(getattr(item, "code", "") or "") for item in items}

async def _load_theme_map(candidate_codes: set[str]) -> tuple[dict[str, dict], list[str]]:
    """加载当日热门题材/行业，并映射到候选池。

    热门概念取前 8、热门行业取前 5；成分股取交集后按排名和涨幅折算强度，
    同一只股票命中多个题材时取最大强度并记录题材名称。
    """
    if not candidate_codes:
        return {}, []
    try:
        concepts, industries = await asyncio.gather(get_ths_hot_concept(), get_ths_hot_industry())
    except Exception as error:
        logger.warning("潜力股热门题材获取失败: %s", error)
        return {}, []

    theme_map: dict[str, dict] = {}
    display_themes: list[str] = []
    entries: list[tuple[dict, float]] = []
    for concept in (concepts or [])[:_THEME_CONCEPT_LIMIT]:
        name = str(concept.get("name") or "").strip()
        if name:
            display_themes.append(name)
        entries.append((concept, 1.0))
    for industry in (industries or [])[:_THEME_INDUSTRY_LIMIT]:
        entries.append((industry, 0.8))

    for entry, weight in entries:
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        try:
            payload = await get_concept_constituents(name, quote_codes=[])
        except Exception as error:  # noqa: BLE001 - 单个题材缺成分股不影响其他题材
            logger.debug("潜力股题材成分获取失败 name=%s: %s", name, error)
            continue
        codes = _constituent_codes(payload) & candidate_codes
        if not codes:
            continue
        rank = _float_or_none(entry.get("rank")) or 99.0
        change = _float_or_none(entry.get("change_pct")) or 0.0
        base = max(0.0, 1.0 - (rank - 1) * 0.1)
        momentum = min(0.3, max(0.0, change / 10.0))
        strength = min(1.0, (base + momentum) * weight)
        for code in codes:
            existing = theme_map.get(code)
            if existing is None:
                theme_map[code] = {"strength": strength, "themes": [name]}
            else:
                existing["strength"] = max(existing["strength"], strength)
                if name not in existing["themes"]:
                    existing["themes"].append(name)
    return theme_map, display_themes[:8]
