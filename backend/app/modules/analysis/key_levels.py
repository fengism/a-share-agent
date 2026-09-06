"""个股分析关键点位的行情计算与结果覆盖。"""

from __future__ import annotations

import logging
from typing import cast

from app.financial_data.stock.quotes.key_levels import KeyLevels, calculate_key_levels
from app.financial_data.stock.quotes.kline import get_kline
from app.modules.analysis.models import AnalysisResult

logger = logging.getLogger(__name__)


async def resolve_key_levels(code: str) -> KeyLevels:
    """加载日 K 并计算关键点位；失败时返回空结果。"""
    try:
        kline = await get_kline(code, period="daily", adjust="qfq")
        return calculate_key_levels(kline.items)
    except Exception as error:
        logger.warning("关键点位计算失败: code=%s, error=%s", code, error)
        return KeyLevels()


def apply_key_levels(result: AnalysisResult, levels: KeyLevels) -> AnalysisResult:
    """用程序计算结果覆盖模型生成的点位，空结果也不回退到模型值。"""
    technical = result.technical.model_copy(
        update={
            "support_level": levels.support,
            "resistance_level": levels.resistance,
        }
    )
    updates: dict[str, object] = {"technical": technical}
    if levels.current_price is not None:
        updates["current_price"] = levels.current_price
    return cast(AnalysisResult, result.model_copy(update=updates))


__all__ = ["apply_key_levels", "resolve_key_levels"]
