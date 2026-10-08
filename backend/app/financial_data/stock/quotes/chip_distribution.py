"""基于日 K 与换手率在本地估算个股筹码分布。"""

from __future__ import annotations

import math
from bisect import bisect_right

from app.core.exceptions import InvalidRequestError
from app.core.market import is_hk_code
from app.domain.market import KlineItem
from app.financial_data.stock.quotes.chip_schemas import (
    ChipCostRange,
    ChipDistribution,
    ChipHistogramItem,
)
from app.financial_data.stock.quotes.kline import get_kline


def _linspace(start: float, stop: float, size: int) -> list[float]:
    if size < 2:
        raise ValueError("grid_size 至少为 2")
    step = (stop - start) / (size - 1)
    return [start + index * step for index in range(size)]


def _triangular_weights(grid: list[float], low: float, high: float, avg: float) -> list[float]:
    """将单日成交筹码按以均价为峰值的三角分布映射到价格网格。"""
    weights = [0.0] * len(grid)
    if not all(math.isfinite(value) for value in (low, high, avg)) or high < low:
        return weights
    if high - low < 1e-9:
        nearest = min(range(len(grid)), key=lambda index: abs(grid[index] - low))
        weights[nearest] = 1.0
        return weights

    avg = min(max(avg, low), high)
    for index, price in enumerate(grid):
        if low <= price <= avg:
            weights[index] = (price - low) / (avg - low) if avg - low > 1e-9 else 1.0
        elif avg < price <= high:
            weights[index] = (high - price) / (high - avg) if high - avg > 1e-9 else 1.0

    total = sum(weights)
    if total > 0:
        return [weight / total for weight in weights]

    # 当振幅小于网格步长时，把当日筹码落到离均价最近的网格点，不能丢掉当日换手。
    nearest = min(range(len(grid)), key=lambda index: abs(grid[index] - avg))
    weights[nearest] = 1.0
    return weights


def _price_at_quantile(grid: list[float], cumulative: list[float], quantile: float) -> float:
    """等价于 ``numpy.interp(quantile, cumulative, grid)`` 的一维线性插值。"""
    index = bisect_right(cumulative, quantile)
    if index <= 0:
        return grid[0]
    if index >= len(cumulative):
        return grid[-1]
    previous_cumulative = cumulative[index - 1]
    current_cumulative = cumulative[index]
    if current_cumulative <= previous_cumulative:
        return grid[index]
    position = (quantile - previous_cumulative) / (current_cumulative - previous_cumulative)
    return grid[index - 1] + position * (grid[index] - grid[index - 1])


def calculate_chip_distribution(
    items: list[KlineItem],
    *,
    code: str = "",
    grid_size: int = 300,
    decay: float = 1.0,
) -> ChipDistribution:
    """按日期升序递推历史筹码，并计算获利比例、成本区间与筹码峰。"""
    if grid_size < 2:
        raise ValueError("grid_size 至少为 2")
    if not math.isfinite(decay) or decay <= 0:
        raise ValueError("decay 必须为正数")

    bars = sorted(
        (
            item
            for item in items
            if item.turnover_pct is not None
            and all(
                math.isfinite(value)
                for value in (item.high, item.low, item.close, item.turnover_pct)
            )
            and item.high > 0
            and item.high >= item.low
        ),
        key=lambda item: item.date,
    )
    if not bars:
        raise ValueError("chip_distribution: 有效行数为 0（检查停牌日、换手率或价格字段）")

    low = min(item.low for item in bars)
    high = max(item.high for item in bars)
    padding = (high - low) * 0.02 or max(low * 0.02, 0.01)
    grid = _linspace(low - padding, high + padding, grid_size)

    chips: list[float] | None = None
    for item in bars:
        turnover = min(max(float(item.turnover_pct) / 100.0 * decay, 0.0), 1.0)
        average = (float(item.high) + float(item.low) + float(item.close)) / 3.0
        weights = _triangular_weights(grid, float(item.low), float(item.high), average)
        if sum(weights) <= 0:
            continue
        if chips is None:
            # 窗口首日代表期初全部流通筹码，避免把窗口内少量换手错误归一成 100%。
            chips = weights.copy()
            continue
        chips = [old * (1.0 - turnover) + new * turnover for old, new in zip(chips, weights, strict=True)]

    if chips is None:
        raise RuntimeError("chip_distribution: 所有交易日的价格区间都无效，无法构建分布")
    total = sum(chips)
    if total <= 0:
        raise RuntimeError("chip_distribution: 筹码总量为 0，无法计算指标")
    chips = [value / total for value in chips]

    cumulative: list[float] = []
    running_total = 0.0
    for value in chips:
        running_total += value
        cumulative.append(running_total)

    p05, p15, p85, p95 = (
        _price_at_quantile(grid, cumulative, quantile) for quantile in (0.05, 0.15, 0.85, 0.95)
    )
    current_price = float(bars[-1].close)
    peak_index = max(range(len(chips)), key=chips.__getitem__)
    resolved_code = code or bars[-1].code

    return ChipDistribution(
        code=resolved_code,
        as_of_date=bars[-1].date,
        price=current_price,
        profit_ratio=sum(chip for price, chip in zip(grid, chips, strict=True) if price <= current_price),
        avg_cost=sum(price * chip for price, chip in zip(grid, chips, strict=True)),
        cost_90=ChipCostRange(low=p05, high=p95),
        cost_70=ChipCostRange(low=p15, high=p85),
        concentration_90=(p95 - p05) / (p95 + p05) if p95 + p05 else None,
        concentration_70=(p85 - p15) / (p85 + p15) if p85 + p15 else None,
        peak_price=grid[peak_index],
        histogram=[
            ChipHistogramItem(price=price, ratio=chip)
            for price, chip in zip(grid, chips, strict=True)
            if chip > 1e-6
        ],
    )


async def get_chip_distribution(
    code: str,
    *,
    grid_size: int = 300,
    decay: float = 1.0,
) -> ChipDistribution:
    """加载前复权日 K 后在本地计算个股筹码分布。"""
    if is_hk_code(code):
        raise InvalidRequestError("港股暂无每日换手率数据，暂不支持筹码分布计算")

    kline = await get_kline(
        code,
        period="daily",
        adjust="qfq",
        require_turnover=True,
    )
    return calculate_chip_distribution(
        kline.items,
        code=kline.code,
        grid_size=grid_size,
        decay=decay,
    )
