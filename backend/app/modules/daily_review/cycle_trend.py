"""情绪周期历史趋势：把逐日复盘摘要拼成周期序列与阶段胜率。

只做确定性聚合（不调用 LLM）：阶段序列、涨停/炸板/涨跌比、次日指数表现，
以及「同一情绪阶段次日上涨概率」这类可验证的经验数据，供复盘 Prompt 定位周期位置。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.daily_review.models import (
    CycleStageStat,
    CycleTrend,
    CycleTrendPoint,
    DailyReviewCycleRecord,
)

# 情绪周期的自然推进顺序，用于判断阶段是升级、降级还是轮转。
_STAGE_ORDER = ("冰点", "修复回暖", "主升共振", "高位分化", "退潮杀跌")
_STAGE_RANK = {stage: rank for rank, stage in enumerate(_STAGE_ORDER)}


def _index_change_pct(record: DailyReviewCycleRecord) -> float | None:
    for move in record.indices:
        if "上证" in move.name:
            return move.change_pct
    return record.indices[0].change_pct if record.indices else None


def _transition(previous: str, current: str) -> str:
    if not previous or not current:
        return ""
    if previous == current:
        return "延续"
    previous_rank = _STAGE_RANK.get(previous)
    current_rank = _STAGE_RANK.get(current)
    if previous_rank is None or current_rank is None:
        return "切换"
    if current_rank > previous_rank:
        return "升级"
    if previous_rank - current_rank == 1:
        return "降级"
    return "切换"


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _stage_stats(points: list[CycleTrendPoint]) -> list[CycleStageStat]:
    buckets: dict[str, list[int]] = {}
    for index, point in enumerate(points):
        if point.stage:
            buckets.setdefault(point.stage, []).append(index)
    stats: list[CycleStageStat] = []
    for stage, indexes in buckets.items():
        next_changes: list[float] = []
        next_deltas: list[float] = []
        for index in indexes:
            if index + 1 >= len(points):
                continue
            # points[index].next_index_change_pct 就是该阶段次日的指数涨跌。
            following_change = points[index].next_index_change_pct
            if following_change is not None:
                next_changes.append(float(following_change))
            current = points[index].limit_up_count
            following = points[index + 1].limit_up_count
            if current is not None and following is not None:
                next_deltas.append(float(following - current))
        stats.append(
            CycleStageStat(
                stage=stage,
                occurrences=len(indexes),
                next_day_up_ratio=(
                    sum(1 for change in next_changes if change > 0) / len(next_changes)
                    if next_changes
                    else None
                ),
                avg_next_day_index_change_pct=_average(next_changes),
                avg_limit_up_delta=_average(next_deltas),
            )
        )
    stats.sort(key=lambda stat: -stat.occurrences)
    return stats


def build_cycle_trend(records: Sequence[DailyReviewCycleRecord], *, days: int = 20) -> CycleTrend:
    """按日期升序聚合最近 `days` 条复盘摘要（纯函数，便于测试）。"""
    ordered = sorted(records, key=lambda record: record.date)[-days:] if days > 0 else []
    points: list[CycleTrendPoint] = []
    for index, record in enumerate(ordered):
        following = ordered[index + 1] if index + 1 < len(ordered) else None
        previous = ordered[index - 1] if index > 0 else None
        points.append(
            CycleTrendPoint(
                date=record.date,
                stage=record.stage,
                ladder_health=record.ladder_health,
                limit_up_count=record.limit_up_count,
                limit_down_count=record.limit_down_count,
                break_rate=record.break_rate,
                up_down_ratio=record.up_down_ratio,
                index_change_pct=_index_change_pct(record),
                next_index_change_pct=_index_change_pct(following) if following is not None else None,
                stage_transition=_transition(previous.stage, record.stage) if previous is not None else "",
            )
        )
    note = ""
    if not points:
        note = "暂无历史复盘样本，尚未形成情绪周期坐标。"
    elif len(points) == 1:
        note = "仅有一个交易日样本，趋势判断参考价值有限。"
    return CycleTrend(points=points, stage_stats=_stage_stats(points), note=note)
