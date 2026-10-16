"""按交易日存放的全局复盘摘要（情绪周期趋势 + 次日自检的数据源）。

只存市场级事实与复盘结论（情绪阶段、涨停/炸板、主要指数、观察标的），不含用户数据，
因此可以跨用户共享；`pipeline` 用历史上的摘要给模型提供周期坐标，并在次日校验昨日预判。
落库到 market 库的 `daily_review_cycle_records`（进程重启/多 worker 均命中）。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Sequence

from app.infrastructure.persistence.connection import get_connection, unit_of_work
from app.modules.daily_review.models import (
    DailyReviewCycleRecord,
    DailyReviewDataSnapshot,
    DailyReviewIndexMove,
    DailyReviewSentimentCycle,
    DailyReviewWatchItem,
)
from app.modules.daily_review.review_builder import limit_break_rate

logger = logging.getLogger(__name__)

_CYCLE_RECORD_PREFIX = "daily_review_cycle:"
# 趋势只看最近一段，但保留更久以便回溯；日期键本身也保证可长期存放。
_CYCLE_RECORD_MAX_AGE_DAYS = 180
_CYCLE_INDEX_NAMES = ("上证指数", "深证成指", "创业板指")


def cycle_record_key(date_text: str) -> str:
    return f"{_CYCLE_RECORD_PREFIX}{date_text}"


def build_cycle_record(
    *,
    date_text: str,
    snapshot: DailyReviewDataSnapshot,
    sentiment_cycle: DailyReviewSentimentCycle | None = None,
    watchlist: Sequence[DailyReviewWatchItem] = (),
    key_levels: Sequence[str] = (),
) -> DailyReviewCycleRecord:
    """从复盘快照与复盘结论里抽出紧凑的当日摘要（不做任何 LLM 调用）。"""
    breadth = snapshot.market_statistics or {}
    up_count = breadth.get("up_count")
    down_count = breadth.get("down_count")
    up_down_ratio: float | None = None
    if isinstance(up_count, int) and isinstance(down_count, int) and down_count > 0:
        up_down_ratio = up_count / down_count
    return DailyReviewCycleRecord(
        date=date_text,
        stage=sentiment_cycle.stage if sentiment_cycle else "",
        ladder_health=sentiment_cycle.ladder_health if sentiment_cycle else "",
        indices=_index_moves(snapshot),
        limit_up_count=_as_int(breadth.get("limit_up_count")),
        limit_down_count=_as_int(breadth.get("limit_down_count")),
        up_down_ratio=up_down_ratio,
        break_rate=limit_break_rate(snapshot),
        watchlist=[item.model_copy(deep=True) for item in watchlist],
        key_levels=[level for level in key_levels if level.strip()],
    )


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _index_moves(snapshot: DailyReviewDataSnapshot) -> list[DailyReviewIndexMove]:
    majors: list[DailyReviewIndexMove] = []
    others: list[DailyReviewIndexMove] = []
    for item in snapshot.indices:
        name = str(item.get("name") or "").strip()
        change = item.get("change_pct")
        if not name or not isinstance(change, (int, float)):
            continue
        move = DailyReviewIndexMove(
            code=str(item.get("code") or "").strip(),
            name=name,
            change_pct=float(change),
        )
        others.append(move)
        if name in _CYCLE_INDEX_NAMES:
            majors.append(move)
    # 优先记录三大指数；行情源没有它们时退化为快照里的前几个指数。
    return majors or others[:3]


def _row_to_record(payload: str) -> DailyReviewCycleRecord | None:
    try:
        raw = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return DailyReviewCycleRecord.model_validate(raw)
    except ValueError:
        logger.warning("复盘周期记录损坏，已跳过: %s", payload[:80])
        return None


def save_cycle_record(record: DailyReviewCycleRecord) -> None:
    """UPSERT 当日摘要（日期为键，重复写入以前一次为准）。"""
    cutoff = time.time() - _CYCLE_RECORD_MAX_AGE_DAYS * 24 * 60 * 60
    with unit_of_work() as work:
        work.connection.execute(
            """
            INSERT INTO daily_review_cycle_records(cycle_date, result_json, generated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cycle_date) DO UPDATE SET
                result_json = excluded.result_json,
                generated_at = excluded.generated_at
            """,
            (record.date, json.dumps(record.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")), time.time()),
        )
        work.connection.execute(
            "DELETE FROM daily_review_cycle_records WHERE generated_at <= ?",
            (cutoff,),
        )


def load_cycle_record(date_text: str) -> DailyReviewCycleRecord | None:
    row = get_connection().execute(
        "SELECT result_json FROM daily_review_cycle_records WHERE cycle_date = ?",
        (date_text,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_record(row["result_json"])


def previous_cycle_record(date_text: str) -> DailyReviewCycleRecord | None:
    """取严格早于 `date_text` 的最近一条记录（用于次日自检）。"""
    row = get_connection().execute(
        "SELECT result_json FROM daily_review_cycle_records WHERE cycle_date < ? ORDER BY cycle_date DESC LIMIT 1",
        (date_text,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_record(row["result_json"])


def recent_cycle_records(limit: int, *, before: str | None = None) -> list[DailyReviewCycleRecord]:
    """按日期倒序取最近 `limit` 条记录，返回升序列表。

    `before` 为排他上界：生成某日复盘时，历史趋势只能看到该日之前的摘要，
    否则写入当日摘要会改变当日 Prompt，导致共享输出缓存与后台预热全部失效。
    """
    if limit <= 0:
        return []
    if before:
        rows = get_connection().execute(
            "SELECT result_json FROM daily_review_cycle_records WHERE cycle_date < ? ORDER BY cycle_date DESC LIMIT ?",
            (before, limit),
        ).fetchall()
    else:
        rows = get_connection().execute(
            "SELECT result_json FROM daily_review_cycle_records ORDER BY cycle_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    records = [record for record in (_row_to_record(row["result_json"]) for row in rows) if record is not None]
    records.reverse()
    return records
