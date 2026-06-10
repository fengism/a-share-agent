import asyncio
from types import SimpleNamespace

from app.services.market import dragon_tiger


def test_get_dragon_tiger_list_falls_back_to_previous_dates(monkeypatch):
    """get_dragon_tiger_list should try earlier dates until the provider returns data."""
    seen_dates = []

    monkeypatch.setattr(dragon_tiger.cache, "get", lambda key: None)
    monkeypatch.setattr(dragon_tiger.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        dragon_tiger,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(fetch_dragon_tiger_daily_list=lambda date: []),
    )

    async def fake_call_blocking(func, *args, **kwargs):
        candidate_date = args[0]
        seen_dates.append(candidate_date)
        if len(seen_dates) == 2:
            return [{"code": "000001", "report_date": candidate_date}]
        return []

    monkeypatch.setattr(dragon_tiger, "call_blocking", fake_call_blocking)

    result = asyncio.run(dragon_tiger.get_dragon_tiger_list("2026-06-10"))

    assert seen_dates[:2] == ["2026-06-10", "2026-06-09"]
    assert result == [{"code": "000001", "report_date": "2026-06-09"}]


def test_get_dragon_tiger_detail_uses_eastmoney_provider(monkeypatch):
    """get_dragon_tiger_detail should return the provider payload as-is."""
    monkeypatch.setattr(dragon_tiger.cache, "get", lambda key: None)
    monkeypatch.setattr(dragon_tiger.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        dragon_tiger,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(fetch_dragon_tiger_stock_detail=lambda code, report_date: []),
    )

    async def fake_call_blocking(func, *args, **kwargs):
        assert args == ("000001", "2026-06-10")
        return [{"营业部": "机构专用", "买入额": 1000}]

    monkeypatch.setattr(dragon_tiger, "call_blocking", fake_call_blocking)

    result = asyncio.run(dragon_tiger.get_dragon_tiger_detail("000001", "2026-06-10"))

    assert result == [{"营业部": "机构专用", "买入额": 1000}]
