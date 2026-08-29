"""估值结果加权与汇总。"""

import logging
import math

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


def _adjust_method_weights(
    fair_values: dict[str, ValuationMethodResult | DCFValuationResult], base_weights: dict[str, float]
) -> dict[str, float]:
    """根据置信度、数据质量和方法一致性调整权重并归一化。

    Param:
        fair_values: 方法名到估值结果的字典
        base_weights: 基础权重字典
    Return:
        归一化后的权重字典
    """
    eligible_items = {
        method: item
        for method, item in fair_values.items()
        if item.available
        and item.per_share_value is not None
        and math.isfinite(item.per_share_value)
        and item.per_share_value > 0
        and math.isfinite(base_weights.get(method, 0))
        and base_weights.get(method, 0) > 0
    }
    positive_values = sorted(
        item.per_share_value
        for item in eligible_items.values()
        if item.per_share_value is not None and item.per_share_value > 0
    )
    consensus_median = None
    if len(positive_values) >= 3:
        mid = len(positive_values) // 2
        consensus_median = (
            positive_values[mid] if len(positive_values) % 2 else (positive_values[mid - 1] + positive_values[mid]) / 2
        )

    raw_weights = {}
    for method, item in eligible_items.items():
        confidence = 0.5 if item.confidence_score is None else item.confidence_score
        if not math.isfinite(confidence):
            confidence = 0.0
        confidence = max(0.0, min(confidence, 1.0))
        data_quality = item.data_quality_score
        if not math.isfinite(data_quality):
            data_quality = 0.0
        data_quality = max(0.0, min(data_quality, 1.0))
        consensus_penalty = 1.0
        if consensus_median is not None:
            if item.per_share_value is None or item.per_share_value <= 0:
                consensus_penalty = 0.25
            else:
                ratio = max(
                    item.per_share_value / consensus_median,
                    consensus_median / item.per_share_value,
                )
                if ratio > 2:
                    consensus_penalty = max(0.25, 2 / ratio)
        raw_weight = base_weights[method] * confidence * data_quality * consensus_penalty
        raw_weights[method] = raw_weight if math.isfinite(raw_weight) else 0.0

    total = sum(raw_weights.values())
    if not math.isfinite(total) or total <= 0:
        return {}

    normalized = {method: weight / total for method, weight in raw_weights.items()}
    rounded = {method: round(weight, 4) for method, weight in normalized.items()}
    largest_method = max(sorted(normalized), key=normalized.__getitem__)
    rounded[largest_method] = round(
        rounded[largest_method] + (1.0 - sum(rounded.values())),
        4,
    )
    return rounded


def _apply_weights(
    fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]
) -> None:
    """将权重写回各估值方法对象。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        无
    """
    for method, item in fair_values.items():
        item.weight = weights.get(method)


def _build_blended_value(
    fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]
) -> float | None:
    """按权重加权得到综合公允每股价值。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        加权后的每股公允价值，无权重时返回 None
    """
    if not weights:
        return None
    weighted_values = []
    for method, weight in weights.items():
        if not math.isfinite(weight):
            return None
        if weight <= 0:
            continue
        item = fair_values.get(method)
        if (
            item is None
            or not item.available
            or item.per_share_value is None
            or not math.isfinite(item.per_share_value)
        ):
            return None
        weighted_values.append(item.per_share_value * weight)
    if not weighted_values:
        return None
    blended_value = sum(weighted_values)
    return round(blended_value, 2) if math.isfinite(blended_value) else None


def _build_blended_range(
    fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]
) -> list[float] | None:
    """按权重加权得到综合公允区间。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        [下限, 上限] 列表，缺失区间时返回 None
    """
    ranges = []
    for method, weight in weights.items():
        if not math.isfinite(weight):
            return None
        if weight <= 0:
            continue
        item = fair_values.get(method)
        if item is None or not item.available:
            return None
        value_range = item.value_range
        if value_range is None or len(value_range) != 2:
            return None
        if not all(math.isfinite(endpoint) for endpoint in value_range):
            return None
        low, high = sorted(value_range)
        ranges.append(((low, high), weight))
    if not ranges:
        return None
    low = sum(value_range[0] * weight for value_range, weight in ranges)
    high = sum(value_range[1] * weight for value_range, weight in ranges)
    if not math.isfinite(low) or not math.isfinite(high):
        return None
    return [round(low, 2), round(high, 2)]


def _build_valuation_view(
    fair_value_range: list[float] | None, blended_fair_value: float | None, current_price: float | None
) -> str | None:
    """根据当前价与公允区间判断估值倾向。

    Param:
        fair_value_range: 公允价值区间
        blended_fair_value: 综合公允价值
        current_price: 当前股价
    Return:
        高估/低估/基本合理 文本，缺失数据时返回 None
    """
    if current_price is None or not math.isfinite(current_price) or current_price <= 0:
        return None
    if (
        fair_value_range is not None
        and len(fair_value_range) == 2
        and all(math.isfinite(endpoint) for endpoint in fair_value_range)
    ):
        low, high = sorted(fair_value_range)
        if current_price < low * 0.9:
            return "低估"
        if current_price > high * 1.1:
            return "高估"
        return "基本合理"
    if blended_fair_value is None or not math.isfinite(blended_fair_value):
        return None
    diff_pct = (blended_fair_value - current_price) / current_price * 100
    if diff_pct >= 15:
        return "低估"
    if diff_pct <= -15:
        return "高估"
    return "基本合理"


def _build_valuation_summary(
    profile: ValuationProfile, fair_value_range: list[float] | None, valuation_view: str | None
) -> str | None:
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
