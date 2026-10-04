"""K 线历史窗口上限测试：起始日期收敛到 10 年内。"""

from __future__ import annotations

from datetime import date

import pytest

from app.financial_data.stock.quotes.kline import _clamp_start_date


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # 区间本身就在 10 年内，保持不变
        (date(2025, 9, 30), date(2026, 10, 2), date(2025, 9, 30)),
        (date(2020, 1, 1), date(2026, 10, 2), date(2020, 1, 1)),
        (date(2026, 10, 2), date(2026, 10, 2), date(2026, 10, 2)),
        # 早于 10 年窗口，收敛到 end - 10 年
        (date(2010, 1, 1), date(2026, 10, 2), date(2016, 10, 2)),
        (date(2016, 1, 1), date(2026, 10, 2), date(2016, 10, 2)),
    ],
)
def test_clamp_start_date_keeps_within_ten_years(start: date, end: date, expected: date) -> None:
    assert _clamp_start_date(start, end) == expected


def test_clamp_handles_leap_day_boundary() -> None:
    # 2024-02-29 往前 10 年落在无效日期，回退到 2 月 28 日
    assert _clamp_start_date(date(2000, 1, 1), date(2024, 2, 29)) == date(2014, 2, 28)


def test_clamp_never_exceeds_end_date() -> None:
    end = date(2026, 10, 2)
    assert _clamp_start_date(date(1990, 1, 1), end) <= end
