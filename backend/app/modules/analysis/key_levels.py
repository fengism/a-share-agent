"""个股分析关键点位的行情计算与结果覆盖。"""

from __future__ import annotations

import logging
from typing import cast

from app.core.market import is_hk_code
from app.financial_data.stock.quotes.key_levels import KeyLevels, calculate_key_levels
from app.financial_data.stock.quotes.kline import get_kline
from app.modules.analysis.models import AnalysisResult

logger = logging.getLogger(__name__)


async def resolve_key_levels(code: str) -> KeyLevels:
    """加载日 K 并计算关键点位；失败时返回空结果。"""
    try:
        # 港股 qfq 依赖一次性导入的复权因子 CSV，覆盖不全时回落新浪上游更慢也更容易
        # 缺数；关键点位只需要价格序列，用不复权口径更稳。
        adjust = "none" if is_hk_code(code) else "qfq"
        kline = await get_kline(code, period="daily", adjust=adjust)
        return calculate_key_levels(kline.items)
    except Exception as error:
        logger.warning("关键点位计算失败: code=%s, error=%s", code, error)
        return KeyLevels()


def _has_levels(levels: KeyLevels) -> bool:
    """是否真的算出了点位（而不是 resolve_key_levels 失败后的空壳）。"""
    return levels.support is not None or levels.resistance is not None


def apply_key_levels(result: AnalysisResult, levels: KeyLevels) -> AnalysisResult:
    """用程序计算结果覆盖模型生成的点位。

    只有真的算出点位时才覆盖。K 线拉取/计算失败时保留模型给出的值：此前空结果会
    无条件把 support_level / resistance_level 清空，并随 AnalysisResult 落盘 + 进缓存，
    用户看到的「无支撑/压力位」无法区分「今天算不出来」和「确实没有关键点位」。
    """
    if not _has_levels(levels):
        return result
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
