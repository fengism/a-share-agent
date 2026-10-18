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


def _consensus_median(values: list[float]) -> float | None:
    """计算有效方法估值的中位数。"""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _consensus_penalty(value: float | None, median: float | None) -> float:
    """按与共识中位数的偏离程度连续惩罚异常方法。

    旧实现只在偏离超过 2 倍时一次性降权，1.9 倍的异常值仍会拿到全权重；
    这里从 1.5 倍开始平滑降权，避免单一方法把综合中枢拉偏。

    Param:
        value: 方法每股价值
        median: 有效方法估值中位数
    Return:
        0.2-1.0 的惩罚系数
    """
    if (
        value is None
        or not math.isfinite(value)
        or value <= 0
        or median is None
        or not math.isfinite(median)
        or median <= 0
    ):
        return 0.25
    ratio = max(value / median, median / value)
    if not math.isfinite(ratio):
        return 0.25
    if ratio <= 1.5:
        return 1.0
    return max(0.2, (1.5 / ratio) ** 2)


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
    # 单一方法不足以构成“综合估值”，否则会把 DCF 等单模型结果当成结论。
    if len(eligible_items) < 2:
        return {}
    consensus_median = _consensus_median(
        [
            item.per_share_value
            for item in eligible_items.values()
            if item.per_share_value is not None and math.isfinite(item.per_share_value) and item.per_share_value > 0
        ]
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
        consensus_penalty = _consensus_penalty(item.per_share_value, consensus_median)
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


def _weighted_quantile(pairs: list[tuple[float, float]], quantile: float) -> float | None:
    """按权重计算分位数。"""
    ordered = sorted(
        (value, weight)
        for value, weight in pairs
        if math.isfinite(value) and value > 0 and math.isfinite(weight) and weight > 0
    )
    total = sum(weight for _, weight in ordered)
    if not ordered or total <= 0:
        return None
    threshold = total * quantile
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return value
    return ordered[-1][0]


def _build_blended_range(
    fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]
) -> list[float] | None:
    """按权重加权得到综合公允区间，并覆盖方法间分歧。

    只对有效区间按权重归一化，避免某个方法缺区间导致整体区间为空；
    同时把区间扩展到方法估值分布的四分位范围，防止“方法打架”时
    区间反而被平均得过窄。

    Param:
        fair_values: 方法名到估值结果的字典
        weights: 方法名到权重的字典
    Return:
        [下限, 上限] 列表，缺失区间时返回 None
    """
    ranges: list[tuple[tuple[float, float], float]] = []
    value_weights: list[tuple[float, float]] = []
    total_weight = 0.0
    for method, weight in weights.items():
        if not math.isfinite(weight) or weight <= 0:
            continue
        item = fair_values.get(method)
        if item is None or not item.available:
            continue
        value = item.per_share_value
        if value is not None and math.isfinite(value) and value > 0:
            value_weights.append((value, weight))
        value_range = item.value_range
        if value_range is None or len(value_range) != 2:
            continue
        if not all(math.isfinite(endpoint) and endpoint > 0 for endpoint in value_range):
            continue
        low, high = sorted(value_range)
        ranges.append(((low, high), weight))
        total_weight += weight
    if not ranges or total_weight <= 0:
        return None
    low = sum(value_range[0] * weight for value_range, weight in ranges) / total_weight
    high = sum(value_range[1] * weight for value_range, weight in ranges) / total_weight
    p25 = _weighted_quantile(value_weights, 0.25)
    p75 = _weighted_quantile(value_weights, 0.75)
    if p25 is not None:
        low = min(low, p25)
    if p75 is not None:
        high = max(high, p75)
    if not math.isfinite(low) or not math.isfinite(high) or low <= 0 or high <= 0:
        return None
    if low > high:
        low, high = high, low
    return [round(low, 2), round(high, 2)]


def _method_dispersion(
    fair_values: dict[str, ValuationMethodResult | DCFValuationResult], weights: dict[str, float]
) -> float | None:
    """计算有效方法估值的最高/最低倍数，用于识别方法分歧。"""
    values = []
    for method, weight in weights.items():
        if not math.isfinite(weight) or weight < 0.05:
            continue
        item = fair_values.get(method)
        if item is None or not item.available:
            continue
        value = item.per_share_value
        if value is None or not math.isfinite(value) or value <= 0:
            continue
        values.append(value)
    if len(values) < 2:
        return None
    return round(max(values) / min(values), 4)


def _build_valuation_view(
    fair_value_range: list[float] | None,
    blended_fair_value: float | None,
    current_price: float | None,
    dispersion: float | None = None,
) -> str | None:
    """根据当前价与公允区间判断估值倾向。

    Param:
        fair_value_range: 公允价值区间
        blended_fair_value: 综合公允价值
        current_price: 当前股价
        dispersion: 方法估值最高/最低倍数
    Return:
        高估/低估/基本合理/分歧较大 文本，缺失数据时返回 None
    """
    if current_price is None or not math.isfinite(current_price) or current_price <= 0:
        return None
    if dispersion is not None and math.isfinite(dispersion) and dispersion > 2.2:
        return "分歧较大"
    if (
        fair_value_range is not None
        and len(fair_value_range) == 2
        and all(math.isfinite(endpoint) for endpoint in fair_value_range)
    ):
        low, high = sorted(fair_value_range)
        if current_price < low:
            return "低估"
        if current_price > high:
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
    profile: ValuationProfile,
    fair_value_range: list[float] | None,
    valuation_view: str | None,
    dispersion: float | None = None,
) -> str | None:
    """构造一句话估值摘要文本。

    Param:
        profile: 估值画像
        fair_value_range: 公允价值区间
        valuation_view: 估值倾向描述
        dispersion: 方法估值最高/最低倍数
    Return:
        摘要字符串，区间或观点缺失时返回兜底说明
    """
    if fair_value_range is None or valuation_view is None:
        return f"{profile.label}画像下，可用估值数据不足，建议结合财务质量和行业景气度进一步验证。"
    if valuation_view == "分歧较大":
        dispersion_text = f"（最高/最低约 {dispersion:.1f} 倍）" if dispersion is not None else ""
        return (
            f"{profile.label}画像下，各估值方法结果分歧较大{dispersion_text}，"
            f"综合区间约为 {fair_value_range[0]:.2f}-{fair_value_range[1]:.2f} 元，仅供参考；"
            "建议优先核对财务口径、同行可比性与增长假设。"
        )
    if valuation_view == "参考性有限":
        return (
            f"{profile.label}画像下，综合区间约为 {fair_value_range[0]:.2f}-{fair_value_range[1]:.2f} 元；"
            "亏损公司未计入研发管线与扭亏预期，方向性判断参考性有限。"
        )
    return f"{profile.label}画像下，综合合理区间约为 {fair_value_range[0]:.2f}-{fair_value_range[1]:.2f} 元，当前估值判断为{valuation_view}。"
