"""基于日 K 行情确定性计算关键支撑位和压力位。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

from app.domain.market import KlineItem
from app.financial_data.stock.quotes.technical import calculate_boll, calculate_ma

_MIN_BARS = 20


@dataclass(frozen=True)
class KeyLevels:
    """关键点位计算结果。"""

    current_price: float | None = None
    support: float | None = None
    resistance: float | None = None


@dataclass(frozen=True)
class _Candidate:
    price: float
    index: int
    volume: float


@dataclass
class _Cluster:
    candidates: list[_Candidate]
    center: float


def calculate_key_levels(
    items: list[KlineItem],
    *,
    lookback: int = 120,
    pivot_window: int = 2,
) -> KeyLevels:
    """从前复权日 K 中计算当前价下方支撑与上方压力。"""
    if lookback < _MIN_BARS or pivot_window < 1:
        raise ValueError("lookback 至少为 20，pivot_window 至少为 1")

    valid_bars = [bar for item in items if (bar := _valid_bar(item)) is not None]
    bars = sorted(valid_bars, key=lambda item: item.date)[-lookback:]
    if len(bars) < _MIN_BARS:
        return KeyLevels()

    current_price = bars[-1].close
    tolerance = _cluster_tolerance(bars, current_price)
    support_candidates, resistance_candidates = _find_pivots(bars, pivot_window)

    support = _select_cluster_level(
        support_candidates,
        current_price=current_price,
        tolerance=tolerance,
        bar_count=len(bars),
        side="support",
    )
    resistance = _select_cluster_level(
        resistance_candidates,
        current_price=current_price,
        tolerance=tolerance,
        bar_count=len(bars),
        side="resistance",
    )

    fallback_support, fallback_resistance = _fallback_levels(bars, current_price)
    support = support if support is not None else fallback_support
    resistance = resistance if resistance is not None else fallback_resistance

    rounded_current = round(current_price, 2)
    rounded_support = _round_level(support, upper_bound=rounded_current)
    rounded_resistance = _round_level(resistance, lower_bound=rounded_current)
    if (
        rounded_support is not None
        and rounded_resistance is not None
        and rounded_support >= rounded_resistance
    ):
        return KeyLevels(current_price=rounded_current)
    return KeyLevels(
        current_price=rounded_current,
        support=rounded_support,
        resistance=rounded_resistance,
    )


def _valid_bar(item: KlineItem) -> KlineItem | None:
    prices = (item.open, item.close, item.high, item.low)
    if not all(math.isfinite(value) and value > 0 for value in prices):
        return None
    if not math.isfinite(item.volume) or item.volume < 0:
        return None
    if item.high < max(item.open, item.close, item.low):
        return None
    if item.low > min(item.open, item.close, item.high):
        return None
    return item


def _cluster_tolerance(bars: list[KlineItem], current_price: float) -> float:
    true_ranges: list[float] = []
    start = max(0, len(bars) - 14)
    for index in range(start, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1].close if index > 0 else bar.close
        true_ranges.append(
            max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        )
    atr = sum(true_ranges) / len(true_ranges)
    return min(max(current_price * 0.01, atr * 0.5), current_price * 0.03)


def _find_pivots(
    bars: list[KlineItem],
    pivot_window: int,
) -> tuple[list[_Candidate], list[_Candidate]]:
    supports: list[_Candidate] = []
    resistances: list[_Candidate] = []
    for index in range(pivot_window, len(bars) - pivot_window):
        bar = bars[index]
        neighbors = bars[index - pivot_window : index] + bars[index + 1 : index + pivot_window + 1]
        if all(bar.low <= neighbor.low for neighbor in neighbors) and any(
            bar.low < neighbor.low for neighbor in neighbors
        ):
            supports.append(_Candidate(bar.low, index, bar.volume))
        if all(bar.high >= neighbor.high for neighbor in neighbors) and any(
            bar.high > neighbor.high for neighbor in neighbors
        ):
            resistances.append(_Candidate(bar.high, index, bar.volume))
    return supports, resistances


def _select_cluster_level(
    candidates: list[_Candidate],
    *,
    current_price: float,
    tolerance: float,
    bar_count: int,
    side: str,
) -> float | None:
    eligible = [
        candidate
        for candidate in candidates
        if (candidate.price < current_price if side == "support" else candidate.price > current_price)
    ]
    if not eligible:
        return None

    volumes = [candidate.volume for candidate in eligible if candidate.volume > 0]
    typical_volume = median(volumes) if volumes else 1.0
    clusters: list[_Cluster] = []
    for candidate in sorted(eligible, key=lambda value: value.price):
        if clusters and abs(candidate.price - clusters[-1].center) <= tolerance:
            cluster = clusters[-1]
            cluster.candidates.append(candidate)
            cluster.center = _weighted_center(cluster.candidates, typical_volume, bar_count)
        else:
            clusters.append(_Cluster(candidates=[candidate], center=candidate.price))

    def rank(cluster: _Cluster) -> tuple[float, float]:
        score = sum(
            3.0
            + 0.5 * min(candidate.volume / typical_volume, 3.0)
            + 1.5 * ((candidate.index + 1) / bar_count)
            for candidate in cluster.candidates
        )
        return score, -abs(current_price - cluster.center)

    return max(clusters, key=rank).center


def _weighted_center(candidates: list[_Candidate], typical_volume: float, bar_count: int) -> float:
    weights = [
        (1.0 + 0.2 * min(candidate.volume / typical_volume, 3.0))
        * (0.5 + 0.5 * ((candidate.index + 1) / bar_count))
        for candidate in candidates
    ]
    return sum(candidate.price * weight for candidate, weight in zip(candidates, weights, strict=True)) / sum(weights)


def _fallback_levels(
    bars: list[KlineItem],
    current_price: float,
) -> tuple[float | None, float | None]:
    closes = [bar.close for bar in bars]
    ma20 = calculate_ma(closes, 20)[-1]
    ma60 = calculate_ma(closes, 60)[-1]
    boll_upper, _, boll_lower = calculate_boll(closes)
    recent_20 = bars[-20:]
    recent_60 = bars[-60:]
    candidates = [
        ma20,
        ma60,
        boll_lower[-1],
        boll_upper[-1],
        min(bar.low for bar in recent_20),
        max(bar.high for bar in recent_20),
        min(bar.low for bar in recent_60),
        max(bar.high for bar in recent_60),
    ]
    values = [value for value in candidates if value is not None and math.isfinite(value) and value > 0]
    supports = [value for value in values if value < current_price]
    resistances = [value for value in values if value > current_price]
    return (max(supports) if supports else None, min(resistances) if resistances else None)


def _round_level(
    value: float | None,
    *,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
) -> float | None:
    if value is None:
        return None
    rounded = round(value, 2)
    if lower_bound is not None and rounded <= lower_bound:
        return None
    if upper_bound is not None and rounded >= upper_bound:
        return None
    return rounded
