"""复盘自检闭环：用次日真实行情校验上一交易日的观察标的与预判。

确定性校验，不调用 LLM：观察标的次日涨跌与是否涨停、主要指数表现、涨停家数变化。
行情优先取本地独立库（market_daily，复盘日次日 16:20 后入库）；当日尚未入库时，
仅对「今天」这一情况回退到实时行情，历史日期绝不使用实时行情冒充。
"""

from __future__ import annotations

import logging
from datetime import date

from app.core.market import market_today
from app.modules.daily_review.models import (
    DailyReviewCycleRecord,
    DailyReviewIndexCheck,
    DailyReviewPreviousCheck,
    DailyReviewWatchCheck,
    IndexSnapshotItem,
)

logger = logging.getLogger(__name__)

# 主板涨停约 10%、创业板/科创板 20%，统一按 9.8% 近似判定是否涨停。
_LIMIT_UP_THRESHOLD = 9.8


def _change_pct(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


async def _local_stock_changes(codes: list[str], verified_date: date) -> dict[str, float]:
    if not codes:
        return {}
    from app.modules.market_daily.service import market_daily_bar_service

    page = await market_daily_bar_service.query(
        instrument_type="stock",
        trade_date=verified_date,
        codes=codes,
        page_size=max(20, len(codes) + 5),
    )
    changes: dict[str, float] = {}
    for bar in page.items:
        change = _change_pct(bar.change_pct)
        if change is not None:
            changes[bar.code] = change
    return changes


async def _realtime_stock_changes(codes: list[str]) -> dict[str, float]:
    if not codes:
        return {}
    from app.financial_data.stock.public import fetch_realtime_quotes

    quotes = await fetch_realtime_quotes(codes)
    changes: dict[str, float] = {}
    for code, quote in quotes.items():
        change = _change_pct(quote.get("change_pct"))
        if change is not None:
            changes[code] = change
    return changes


def _index_checks(
    record: DailyReviewCycleRecord,
    current_indices: list[IndexSnapshotItem],
) -> list[DailyReviewIndexCheck]:
    by_code = {str(item.get("code") or ""): item for item in current_indices}
    by_name = {str(item.get("name") or ""): item for item in current_indices}
    checks: list[DailyReviewIndexCheck] = []
    for move in record.indices:
        current = by_code.get(move.code) or by_name.get(move.name)
        checks.append(
            DailyReviewIndexCheck(
                code=move.code,
                name=move.name,
                previous_change_pct=move.change_pct,
                change_pct=_change_pct(current.get("change_pct")) if current else None,
            )
        )
    return checks


async def build_previous_review_check(
    record: DailyReviewCycleRecord | None,
    *,
    verified_date: date,
    current_indices: list[IndexSnapshotItem],
    current_limit_up_count: int | None,
) -> DailyReviewPreviousCheck | None:
    """把 `record`（上一交易日复盘摘要）与 `verified_date` 的真实行情做对照。

    数据缺失时返回带说明的结论而不是抛错，避免自检失败拖垮当日复盘生成。
    """
    if record is None:
        return None

    watchlist = [item for item in record.watchlist if item.name.strip()]
    codes = [item.code for item in watchlist if item.code]
    changes: dict[str, float] = {}
    notes: list[str] = []
    if codes:
        try:
            changes = await _local_stock_changes(codes, verified_date)
        except Exception:  # noqa: BLE001 - 自检失败不影响复盘生成
            logger.warning("复盘自检读取本地日线失败: date=%s", verified_date.isoformat(), exc_info=True)
            notes.append("本地日线读取失败")
        missing_codes = [code for code in codes if code not in changes]
        if missing_codes and verified_date == market_today():
            try:
                changes.update(await _realtime_stock_changes(missing_codes))
            except Exception:  # noqa: BLE001 - 实时行情不可用只降级为缺失
                logger.warning("复盘自检实时行情不可用: date=%s", verified_date.isoformat(), exc_info=True)
                notes.append("实时行情不可用")

    watch_checks: list[DailyReviewWatchCheck] = []
    for item in watchlist:
        change = changes.get(item.code) if item.code else None
        if change is None:
            watch_checks.append(
                DailyReviewWatchCheck(name=item.name, code=item.code, role=item.role, missing=True)
            )
            continue
        watch_checks.append(
            DailyReviewWatchCheck(
                name=item.name,
                code=item.code,
                role=item.role,
                change_pct=change,
                hit=change > 0,
                limit_up=change >= _LIMIT_UP_THRESHOLD,
            )
        )

    checked = [check for check in watch_checks if not check.missing]
    hit_count = sum(1 for check in checked if check.hit)
    hit_rate = hit_count / len(checked) if checked else None
    if watch_checks and not checked:
        notes.append("观察标的次日行情尚未入库（多在收盘后 16:20 补齐）")
    elif any(check.missing for check in watch_checks):
        notes.append("部分观察标的次日无行情（停牌或未入库）")
    if not watchlist:
        notes.append("上一交易日复盘没有可验证的观察标的")
    if not record.stage:
        notes.append("上一交易日复盘未定位情绪阶段（兜底稿）")

    limit_up_delta: int | None = None
    if isinstance(current_limit_up_count, int) and isinstance(record.limit_up_count, int):
        limit_up_delta = current_limit_up_count - record.limit_up_count

    return DailyReviewPreviousCheck(
        review_date=record.date,
        verified_date=verified_date.isoformat(),
        indices=_index_checks(record, current_indices),
        watchlist=watch_checks,
        hit_count=hit_count,
        checked_count=len(checked),
        hit_rate=hit_rate,
        previous_stage=record.stage,
        limit_up_count=current_limit_up_count,
        previous_limit_up_count=record.limit_up_count,
        limit_up_delta=limit_up_delta,
        note="；".join(notes),
    )
