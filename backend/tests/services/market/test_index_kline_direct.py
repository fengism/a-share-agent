import asyncio

import pandas as pd

from app.services.market import index_kline


def test_index_kline_source_attempts_include_eastmoney_direct(monkeypatch):
    captured = {}

    def fake_fetch(symbol, period, start_date, end_date):
        captured.update({"symbol": symbol, "period": period, "start_date": start_date, "end_date": end_date})
        return pd.DataFrame([{"日期": "2026-05-25", "收盘": "3020"}])

    monkeypatch.setattr(index_kline._eastmoney_provider, "fetch_index_kline_direct", fake_fetch)

    attempts = index_kline._build_index_kline_source_attempts("000001", "daily", "20260521", "20260525")
    eastmoney_attempt = [a for a in attempts if "东方财富" in a.label and "直连" in a.label][0]
    df = asyncio.run(eastmoney_attempt.loader())

    assert captured == {"symbol": "000001", "period": "daily", "start_date": "20260521", "end_date": "20260525"}
    assert df.iloc[0]["收盘"] == "3020"
