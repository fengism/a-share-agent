import pandas as pd
import asyncio

from app.services.stock import intraday


def test_load_intraday_fills_prev_close_and_change_pct_from_basic_info(monkeypatch):
    """_load_intraday backfills prev_close and change_pct from basic info when missing."""
    class Sym:
        raw = "603228"

    source = pd.DataFrame(
        [
            {"time": "09:30", "price": 86.93, "avg_price": 86.93, "volume": 100, "amount": 8693},
            {"time": "09:31", "price": 82.45, "avg_price": 84.00, "volume": 200, "amount": 16490},
        ]
    )

    async def fake_safe_fetch(source_name, fetcher, code, date):
        return source if source_name == "新浪财经分钟直连" else pd.DataFrame()

    async def fake_basic_info(code: str):
        class BasicInfo:
            current_price = 82.45
            market_cap = None
            total_shares = None

        return BasicInfo()

    monkeypatch.setattr(intraday, "_safe_fetch_intraday", fake_safe_fetch)
    monkeypatch.setattr(intraday, "get_basic_info", fake_basic_info, raising=False)

    result = asyncio.run(intraday._load_intraday(Sym(), "2026-05-27"))

    assert result.prev_close == 86.93
    assert result.items[0].change_pct == 0.0
    assert result.items[-1].change_pct == -5.15
