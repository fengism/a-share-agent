import pandas as pd
import pytest

from app.services.stock import financials


@pytest.mark.asyncio
async def test_get_financial_metrics_uses_existing_stock_financials_provider(monkeypatch):
    """get_financial_metrics calls the stock financials provider for balance/profit/cashflow."""
    calls = []

    async def fake_call_blocking(func, *args, **kwargs):
        calls.append((func, kwargs["indicator"]))
        if kwargs["indicator"] == "balance":
            return pd.DataFrame([{"报告期": "2026-06-30", "资产总计": 100, "负债合计": 40, "股东权益合计": 60}])
        if kwargs["indicator"] == "profit":
            return pd.DataFrame([{"报告期": "2026-06-30", "营业总收入": 50, "净利润": 8}])
        return pd.DataFrame([{"报告期": "2026-06-30", "经营活动产生的现金流量净额": 7}])

    monkeypatch.setattr(financials.cache, "get", lambda key: None)
    monkeypatch.setattr(financials.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(financials, "call_blocking", fake_call_blocking)

    result = await financials.get_financial_metrics("603228")

    assert [indicator for _, indicator in calls] == ["balance", "profit", "cashflow"]
    assert all(func.__name__ == "fetch_stock_financials" for func, _ in calls)
    assert result.latest_report_date == "2026-06-30"
    assert result.metrics["资产负债率"] == 0.4
