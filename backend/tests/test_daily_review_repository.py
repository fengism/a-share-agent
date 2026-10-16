"""每日复盘持久化：历史隔离与读路径无副作用。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from app.modules.daily_review import service
from app.modules.daily_review.models import (
    DailyReviewDataSnapshot,
    DailyReviewResult,
    DailyReviewSection,
)
from app.modules.daily_review.persistence import repository

_TZ = ZoneInfo("Asia/Shanghai")
_VOLUME_COMPLETE = {
    "amount": 1.2e12,
    "amount_before_one_day": 1.0e12,
    "amount_average_20_day": 9.0e11,
    "amount_average_60_day": 8.0e11,
}


def _section() -> DailyReviewSection:
    return DailyReviewSection(title="章节", summary="摘要")


def _review(date: str, *, title: str = "每日复盘", market_volume: dict[str, Any] | None = None) -> DailyReviewResult:
    return DailyReviewResult(
        date=date,
        effective_date=date,
        quality_status="complete",
        generation_status="llm",
        title=title,
        generated_at=datetime(2026, 10, 14, 16, 0, tzinfo=_TZ).isoformat(timespec="seconds"),
        market_summary="摘要",
        index_review=_section(),
        hotspot_review=_section(),
        dragon_tiger_review=_section(),
        news_policy_review=_section(),
        data_snapshot=DailyReviewDataSnapshot(market_volume=market_volume or {}),
    )


def _write(path, review: DailyReviewResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(review.model_dump_json(indent=2), encoding="utf-8")


def test_legacy_review_is_hidden_from_regular_users(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repository, "_DATA_DIR", tmp_path)
    _write(tmp_path / "2026-10-14.json", _review("2026-10-14"))

    assert repository.load_daily_review("2026-10-14", 7) is None
    assert repository.load_daily_review("2026-10-14", 7, include_legacy=True) is not None


def test_user_review_wins_over_legacy_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repository, "_DATA_DIR", tmp_path)
    _write(tmp_path / "2026-10-14.json", _review("2026-10-14", title="旧版全局复盘"))
    _write(tmp_path / "users" / "7" / "2026-10-14.json", _review("2026-10-14", title="用户复盘"))

    loaded = repository.load_daily_review("2026-10-14", 7, include_legacy=True)

    assert loaded is not None
    assert loaded.title == "用户复盘"


def test_history_hides_legacy_files_from_regular_users(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repository, "_DATA_DIR", tmp_path)
    _write(tmp_path / "2026-10-13.json", _review("2026-10-13"))
    _write(tmp_path / "users" / "7" / "2026-10-14.json", _review("2026-10-14"))

    regular = repository.list_daily_reviews(7)
    admin = repository.list_daily_reviews(7, can_delete_legacy=True)

    assert [item.date for item in regular] == ["2026-10-14"]
    assert [item.date for item in admin] == ["2026-10-14", "2026-10-13"]
    assert regular[0].can_delete is True
    assert admin[1].can_delete is True


async def test_backfill_does_not_persist_or_mutate_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _review("2026-10-14", market_volume={"amount": 1.2e12})

    async def _stats(target: object, *, use_realtime: bool = False) -> SimpleNamespace:
        return SimpleNamespace(
            amount=1.2e12,
            amount_before_one_day=1.0e12,
            amount_average_20_day=9.0e11,
            amount_average_60_day=8.0e11,
        )

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("读路径不应写回复盘持久化")

    monkeypatch.setattr(service, "get_market_volume_stats", _stats)
    monkeypatch.setattr(repository, "save_daily_review", _forbidden)

    patched = await service._backfill_market_volume_stats(record)

    assert patched is not record
    assert patched.data_snapshot is not None
    assert patched.data_snapshot.market_volume["amount_average_20_day"] == 9.0e11
    assert record.data_snapshot is not None
    assert record.data_snapshot.market_volume == {"amount": 1.2e12}


async def test_backfill_leaves_complete_snapshot_untouched() -> None:
    record = _review("2026-10-14", market_volume=dict(_VOLUME_COMPLETE))

    assert await service._backfill_market_volume_stats(record) is record


async def test_get_daily_review_record_forwards_legacy_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[bool] = []

    def _load(date: str, user_id: int, *, include_legacy: bool = False) -> None:
        seen.append(include_legacy)
        return None

    monkeypatch.setattr(service.repository, "load_daily_review", _load)

    await service.get_daily_review_record("2026-10-14", 7, include_legacy=True)
    await service.get_daily_review_record("2026-10-14", 7)

    assert seen == [True, False]
