import asyncio
from types import SimpleNamespace

import pandas as pd

from app.services.market import sector


def clear_sector_cache() -> None:
    """Remove the dated industry_rankings cache entry."""
    sector.cache.delete(sector.dated_cache_key("industry_rankings"))


def test_get_industry_rankings_falls_back_to_tencent(monkeypatch):
    """get_industry_rankings should use Tencent data when Baidu and EastMoney fail."""
    clear_sector_cache()

    async def fake_call_blocking(func, *args, **kwargs):
        kwargs.pop("semaphore", None)
        return func(*args, **kwargs)

    monkeypatch.setattr(sector, "call_blocking", fake_call_blocking)
    monkeypatch.setattr(
        sector,
        "_get_baidu_provider",
        lambda: SimpleNamespace(fetch_industry_rankings=lambda limit: (_ for _ in ()).throw(RuntimeError("baidu down"))),
    )
    monkeypatch.setattr(
        sector,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(fetch_industry_rankings=lambda limit: (_ for _ in ()).throw(RuntimeError("east down"))),
    )
    monkeypatch.setattr(
        sector,
        "_get_tencent_provider",
        lambda: SimpleNamespace(
            fetch_industry_rankings=lambda: (
                pd.DataFrame([{"板块名称": "AI", "涨跌幅": 1.2, "板块代码": "BK001", "领涨跌股票名称": "科创", "领涨股票-涨跌幅": 5.0}]),
                pd.DataFrame([{"板块名称": "地产", "涨跌幅": -1.5, "板块代码": "BK002", "领涨跌股票名称": "城建", "领涨股票-涨跌幅": -3.0}]),
            )
        ),
    )

    result = asyncio.run(sector.get_industry_rankings())

    assert result["total"] == 2
    assert result["sectors"][0]["name"] == "AI"
    assert result["sectors"][1]["name"] == "地产"
