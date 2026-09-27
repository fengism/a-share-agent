"""国家队行情预热与超时预算的守卫测试。"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from app.financial_data.market.quotes import national_team
from app.financial_data.market.quotes.national_team import (
    _PRICE_ITEM_TIMEOUT_SECONDS,
    _PRICE_TIMEOUT_SECONDS,
    _response_window,
    prewarm_national_team_prices,
)


def test_price_timeout_budget_covers_tdx_latency():
    # TDX 日K 在排队争用下可达 20 秒以上，单标的预算必须宽于该量级
    assert _PRICE_ITEM_TIMEOUT_SECONDS >= 30.0
    # 整批预算需容纳 18 个标的在并发上限下的排队总时长
    assert _PRICE_TIMEOUT_SECONDS >= _PRICE_ITEM_TIMEOUT_SECONDS * 2


def test_response_window_matches_collect_window():
    now = datetime(2026, 9, 27, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    start, end = _response_window(120, now)
    assert end == date(2026, 9, 27)
    assert start == end - timedelta(days=119)


class _FakeIndexDefinition:
    def __init__(self, index_code: str) -> None:
        self.index_code = index_code


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        return datetime(2026, 9, 27, 13, 0, tzinfo=tz)


async def test_prewarm_national_team_prices_warms_all_pools(monkeypatch):
    calls = []

    async def fake_index_kline(symbol, period, start_date, end_date):
        calls.append(("index", symbol, start_date, end_date))

    async def fake_kline(code, **kwargs):
        calls.append(("etf", code, kwargs["start_date"], kwargs["end_date"]))

    monkeypatch.setattr(national_team, "datetime", _FixedDatetime)
    monkeypatch.setattr(national_team, "INDEX_POOL", {"csi300": _FakeIndexDefinition("000301.SH")})
    monkeypatch.setattr(national_team, "ETF_POOL", {"510301": object()})
    monkeypatch.setattr(national_team, "get_index_kline", fake_index_kline)
    monkeypatch.setattr(national_team, "get_kline", fake_kline)

    await prewarm_national_team_prices()

    # 窗口与 _collect_response 默认 120 天完全一致，确保命中同一批缓存键
    assert ("index", "000301", "20260531", "20260927") in calls
    assert ("etf", "510301", "20260531", "20260927") in calls


async def test_prewarm_national_team_prices_swallows_item_failures(monkeypatch):
    failing = AsyncMock(side_effect=RuntimeError("upstream down"))
    monkeypatch.setattr(national_team, "datetime", _FixedDatetime)
    monkeypatch.setattr(national_team, "INDEX_POOL", {"csi300": _FakeIndexDefinition("000301.SH")})
    monkeypatch.setattr(national_team, "ETF_POOL", {"510301": object()})
    monkeypatch.setattr(national_team, "get_index_kline", failing)
    monkeypatch.setattr(national_team, "get_kline", failing)

    # 预热失败不应向调用方（启动流程）传播异常
    await prewarm_national_team_prices()
    assert failing.await_count == 2
