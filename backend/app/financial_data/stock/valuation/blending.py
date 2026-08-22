"""估值结果加权与汇总。"""

import logging

from app.financial_data.stock.valuation.schemas import (
    DCFValuationResult,
    ValuationMethodResult,
    ValuationProfile,
)

logger = logging.getLogger(__name__)


def _base_method_weights(profile: ValuationProfile) -> dict[str, float]:
    """根据股票画像返回各估值方法的基础权重。

    Param:
        profile: 估值画像
    Return:
        方法名到权重的字典
    """
    weights_by_category = {
        "financial": {"pe": 0.12, "pb": 0.58, "ps": 0.08, "peg": 0.07, "dcf": 0.15},
        "cyclical": {"pe": 0.22, "pb": 0.43, "ps": 0.08, "peg": 0.07, "dcf": 0.20},
        "growth": {"pe": 0.18, "pb": 0.12, "ps": 0.28, "peg": 0.22, "dcf": 0.20},
        "stable": {"pe": 0.34, "pb": 0.18, "ps": 0.08, "peg": 0.10, "dcf": 0.30},
        "loss_making": {"pe": 0.0, "pb": 0.25, "ps": 0.55, "peg": 0.0, "dcf": 0.20},
        "general": {"pe": 0.25, "pb": 0.22, "ps": 0.22, "peg": 0.11, "dcf": 0.20},
    }
    return weights_by_category.get(profile.category, weights_by_category["general"])

def _adjust_method_weights(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], base_weights: dict[str, float]) -> dict[str, float]:
    """根据置信度调整估值方法权重并归一化。

    Param:
        fair_values: 方法名到估值结果的字典
        base_weights: 基础权重字典
    Return:
        归一化后的权重字典
    """
    raw_weights = {
        method: base_weights.get(method, 0) * (item.confidence_score or 0.5)
        for method, item in fair_values.items()
        if item.available and item.per_share_value is not None and base_weights.get(method, 0) > 0
    }
    total = sum(raw_weights.values())
    if total <= 0:
        return {}
    return {method: round(weight / total, 4) for method, weight in raw_weights.items()}

def _apply_weights(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]) -> None:
    """将权重写回各估值方法对象。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        无
    """
    for method, item in fair_values.items():
        item.weight = weights.get(method)

def _build_blended_value(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]) -> float | None:
    """按权重加权得到综合公允每股价值。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        加权后的每股公允价值，无权重时返回 None
    """
    if not weights:
        return None
    return round(sum((fair_values[method].per_share_value or 0) * weight for method, weight in weights.items()), 2)

def _build_blended_range(fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]) -> list[float] | None:
    """按权重加权得到综合公允区间。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        [下限, 上限] 列表，缺失区间时返回 None
    """
    ranges = []
    for method, weight in weights.items():
        value_range = fair_values[method].value_range
        if value_range is None or len(value_range) != 2:
            return None
        ranges.append((value_range, weight))
    if not ranges:
        return None
    low = sum(value_range[0] * weight for value_range, weight in ranges)
    high = sum(value_range[1] * weight for value_range, weight in ranges)
    return [round(low, 2), round(high, 2)]

def _build_valuation_view(fair_value_range: list[float] | None, blended_fair_value: float | None, current_price: float | None) -> str | None:
    """根据当前价与公允区间判断估值倾向。

    Param:
        fair_value_range: 公允价值区间
        blended_fair_value: 综合公允价值
        current_price: 当前股价
    Return:
        高估/低估/基本合理 文本，缺失数据时返回 None
    """
    if current_price in (None, 0):
        return None
    if fair_value_range is not None and len(fair_value_range) == 2:
        low, high = fair_value_range
        if current_price < low * 0.9:
            return "低估"
        if current_price > high * 1.1:
            return "高估"
        return "基本合理"
    if blended_fair_value is None:
        return None
    diff_pct = (blended_fair_value - current_price) / current_price * 100
    if diff_pct >= 15:
        return "低估"
    if diff_pct <= -15:
        return "高估"
    return "基本合理"

def _build_valuation_summary(profile: ValuationProfile, fair_value_range: list[float] | None, valuation_view: str | None) -> str | None:
    """构造一句话估值摘要文本。

    Param:
        profile: 估值画像
        fair_value_range: 公允价值区间
        valuation_view: 估值倾向描述
    Return:
        摘要字符串，区间或观点缺失时返回兜底说明
    """
    if fair_value_range is None or valuation_view is None:
        return f"{profile.label}画像下，可用估值数据不足，建议结合财务质量和行业景气度进一步验证。"
    return f"{profile.label}画像下，综合合理区间约为 {fair_value_range[0]:.2f}-{fair_value_range[1]:.2f} 元，当前估值判断为{valuation_view}。"
