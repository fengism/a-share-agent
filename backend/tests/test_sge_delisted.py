"""上金所停更合约识别的测试。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.financial_data.market.quotes.sge_gold import SgeGoldService

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_TODAY = date(2026, 10, 13)


def _service(tmp_path: Path, last_trading_day: date) -> SgeGoldService:
    service = SgeGoldService(
        data_dir=tmp_path,
        now=lambda: datetime(_TODAY.year, _TODAY.month, _TODAY.day, 9, 30, tzinfo=_SHANGHAI_TZ),
    )
    return service


def _history(last_trading_day: date, points: int = 3) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for offset in range(points, 0, -1):
        day = last_trading_day - timedelta(days=offset)
        rows.append({"date": day.isoformat(), "open": 100.0, "close": 101.0, "low": 99.0, "high": 102.0})
    rows.append({"date": last_trading_day.isoformat(), "open": 101.0, "close": 103.0, "low": 100.0, "high": 104.0})
    return rows


def test_fresh_contract_is_not_delisted(tmp_path: Path) -> None:
    service = _service(tmp_path, _TODAY - timedelta(days=1))

    response = service._to_response("Au99.99", "2026-10-13T09:30:00+08:00", _history(_TODAY - timedelta(days=1)), is_stale=False)

    assert response.is_delisted is False


def test_long_holiday_is_not_misjudged(tmp_path: Path) -> None:
    """长假期间最新交易日滞后数天属正常，不应判定停更。"""
    service = _service(tmp_path, _TODAY - timedelta(days=8))

    response = service._to_response("Au99.99", "2026-10-13T09:30:00+08:00", _history(_TODAY - timedelta(days=8)), is_stale=False)

    assert response.is_delisted is False


def test_long_stopped_contract_is_marked_delisted(tmp_path: Path) -> None:
    """Au(T+N2) 这类停更合约必须被标记。"""
    last_day = date(2026, 6, 8)
    service = _service(tmp_path, last_day)

    response = service._to_response("Au(T+N2)", "2026-10-13T09:30:00+08:00", _history(last_day), is_stale=False)

    assert response.is_delisted is True
    assert response.latest is not None
    assert response.latest.date == "2026-06-08"


def test_empty_history_is_not_delisted(tmp_path: Path) -> None:
    service = _service(tmp_path, _TODAY)

    response = service._to_response("Au99.99", "2026-10-13T09:30:00+08:00", [], is_stale=False)

    assert response.is_delisted is False
    assert response.latest is None


def test_unparsable_latest_date_is_not_delisted(tmp_path: Path) -> None:
    service = _service(tmp_path, _TODAY)
    rows = _history(_TODAY)
    rows[-1]["date"] = "not-a-date"

    response = service._to_response("Au99.99", "2026-10-13T09:30:00+08:00", rows, is_stale=False)

    assert response.is_delisted is False


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("Au99.99", False),
        ("Au(T+N1)", True),
        ("Au(T+N2)", True),
        ("Au99.5", True),
        ("iAu100g", True),
        ("Ag(T+D)", False),
    ],
)
def test_real_contract_states(tmp_path: Path, symbol: str, expected: bool) -> None:
    """对照实测：4 个停更合约，其余活跃。"""
    stopped = {
        "Au(T+N1)": date(2026, 8, 27),
        "Au(T+N2)": date(2026, 6, 8),
        "Au99.5": date(2021, 10, 26),
        "iAu100g": date(2025, 6, 4),
    }
    last_day = stopped.get(symbol, date(2026, 10, 12))
    service = _service(tmp_path, last_day)

    response = service._to_response(symbol, "2026-10-13T09:30:00+08:00", _history(last_day), is_stale=False)

    assert response.is_delisted is expected