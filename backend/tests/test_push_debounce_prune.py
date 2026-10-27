"""推送防抖表的回收。

防抖表 ``_recent_dispatches`` 的键是 ``类别:日期``，只写不删会随进程寿命无限增长。
这里验证"过期即清"且清理频率受控（不会每次推送都全表扫描）。
"""

from __future__ import annotations

import pytest

from app.modules.push import dispatcher


@pytest.fixture(autouse=True)
def _reset_debounce_state(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatcher._recent_dispatches.clear()
    monkeypatch.setattr(dispatcher, "_last_debounce_purge", 0.0)
    yield
    dispatcher._recent_dispatches.clear()
    monkeypatch.setattr(dispatcher, "_last_debounce_purge", 0.0)


def test_expired_entries_are_pruned_and_fresh_ones_kept() -> None:
    now = 10_000.0
    dispatcher._recent_dispatches.update(
        {
            "daily_review:2026-01-01": now - dispatcher._DEBOUNCE_WINDOW_SECONDS - 1,
            "daily_review:2026-01-02": now - 5,
        }
    )
    dispatcher._prune_recent_dispatches(now)
    assert list(dispatcher._recent_dispatches) == ["daily_review:2026-01-02"]


def test_prune_runs_at_most_once_per_interval() -> None:
    now = 10_000.0
    dispatcher._recent_dispatches["daily_review:old"] = now - 10_000
    dispatcher._prune_recent_dispatches(now)
    assert dispatcher._recent_dispatches == {}

    # 间隔未到：即使新写入过期项，也不应再次全表扫描。
    dispatcher._recent_dispatches["daily_review:later"] = now - 10_000
    dispatcher._prune_recent_dispatches(now + 1)
    assert "daily_review:later" in dispatcher._recent_dispatches

    # 超过间隔后恢复清理
    dispatcher._prune_recent_dispatches(now + dispatcher._DEBOUNCE_PURGE_INTERVAL_SECONDS + 1)
    assert dispatcher._recent_dispatches == {}


def test_entry_does_not_grow_without_bound_over_many_days() -> None:
    """模拟 400 天每日一次推送：表规模应维持在窗口附近而不是线性增长。"""
    window = dispatcher._DEBOUNCE_WINDOW_SECONDS
    interval = dispatcher._DEBOUNCE_PURGE_INTERVAL_SECONDS
    start = 1_000_000.0
    for day in range(400):
        now = start + day * 86_400
        dispatcher._prune_recent_dispatches(now)
        dispatcher._recent_dispatches[f"daily_review:day-{day}"] = now
    # 每 interval 秒清一次，窗口 180s 内最多留下极少数条目；400 天 = 400 条无清理，
    # 有清理时远小于这个量级。
    assert len(dispatcher._recent_dispatches) < 10
    assert interval > window
