"""K 线数据质量校验：覆盖度下限与内部空洞检测。"""

import pandas as pd
import pytest

from app.core.exceptions import UpstreamEmptyResponseError
from app.financial_data.kline_quality import _weekdays, validate_kline_frame

_START = "2025-10-13"
_END = "2026-10-13"
_TODAY = pd.Timestamp(_END).date()


def _weekday_range(start: str, end: str) -> list[str]:
    """构造仅含工作日的日期序列（无节假日，放宽覆盖度下限）。"""
    days: list[str] = []
    cursor = pd.Timestamp(start)
    while cursor <= pd.Timestamp(end):
        if cursor.weekday() < 5:
            days.append(cursor.strftime("%Y-%m-%d"))
        cursor += pd.Timedelta(days=1)
    return days


def _frame(dates: list[str], base: float = 3000.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": day,
                "open": base,
                "close": base + 1,
                "high": base + 2,
                "low": base - 2,
                "volume": 1e8,
                "amount": 1e10,
            }
            for day in dates
        ]
    )


def _validate(frame: pd.DataFrame, *, require_coverage: bool, period: str = "daily",
              start: str = _START, end: str = _END) -> pd.DataFrame:
    return validate_kline_frame(
        "测试源",
        frame,
        start_date=start,
        end_date=end,
        period=period,
        today=_TODAY,
        require_coverage=require_coverage,
    )


def test_weekdays_matches_business_day_count():
    assert _weekdays(pd.Timestamp(_START).date(), pd.Timestamp(_START).date()) == 0
    assert _weekdays(pd.Timestamp("2026-01-05").date(), pd.Timestamp("2026-01-09").date()) == 5
    assert _weekdays(pd.Timestamp("2026-01-05").date(), pd.Timestamp("2026-01-05").date()) == 0


def test_full_year_passes_with_coverage_required():
    dates = _weekday_range(_START, _END)
    accepted = _validate(_frame(dates), require_coverage=True)
    assert len(accepted) == len(dates)


@pytest.mark.parametrize("keep", [1, 20, 120])
def test_truncated_tail_fails_coverage(keep: int):
    dates = _weekday_range(_START, _END)
    with pytest.raises(UpstreamEmptyResponseError, match="覆盖度不足"):
        _validate(_frame(dates[-keep:]), require_coverage=True)


def test_middle_gap_is_rejected_even_without_coverage():
    """覆盖度关闭时（个股路径），内部空洞仍必须被识别。"""
    dates = _weekday_range(_START, _END)
    with pytest.raises(UpstreamEmptyResponseError, match="超长数据空洞"):
        _validate(_frame(dates[:60] + dates[180:]), require_coverage=False)


def test_spring_festival_gap_is_accepted():
    """A 股长假会造成最长 8 个工作日的空洞，属于合法数据。"""
    dates = _weekday_range(_START, _END)
    truncated_window = [day for day in dates if day <= "2026-02-13" or day >= "2026-02-24"]
    assert _weekdays(pd.Timestamp("2026-02-13").date(), pd.Timestamp("2026-02-24").date()) == 8
    accepted = _validate(_frame(truncated_window), require_coverage=True)
    assert len(accepted) == len(truncated_window)


def test_single_day_request_is_not_constrained():
    """日复盘等单日请求只能拿到 1 根，覆盖度下限不得误伤。"""
    accepted = _validate(
        _frame([_END]), require_coverage=True, start=_END, end=_END
    )
    assert len(accepted) == 1


@pytest.mark.parametrize("listing_start", ["2026-08-13", "2026-10-07"])
def test_young_stock_survives_when_coverage_disabled(listing_start: str):
    """次新股请求一年只能回上市以来的数据，个股路径不得启用覆盖度下限。"""
    dates = _weekday_range(listing_start, _END)
    accepted = _validate(_frame(dates), require_coverage=False)
    assert len(accepted) == len(dates)


def test_young_stock_would_be_killed_if_coverage_enabled(listing_start="2026-08-13"):
    """记录"覆盖度只对指数开启"这一取舍，防止被误加到个股路径。"""
    dates = _weekday_range(listing_start, _END)
    with pytest.raises(UpstreamEmptyResponseError, match="覆盖度不足"):
        _validate(_frame(dates), require_coverage=True)


def test_stale_data_is_still_rejected():
    """窗口对齐但数据停在半年前时，陈旧度校验必须先于覆盖度触发。"""
    dates = _weekday_range("2026-01-02", "2026-03-31")
    with pytest.raises(UpstreamEmptyResponseError, match="数据陈旧"):
        _validate(_frame(dates), require_coverage=True)