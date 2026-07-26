import asyncio
from types import SimpleNamespace

from app.services.market import statistic


def test_get_market_statistics_uses_eastmoney_provider(monkeypatch):
    """get_market_statistics assembles sector, distribution, and limit data from providers."""
    statistic.cache.delete(statistic.dated_cache_key("market_statistics", "2026-05-25"))

    async def fake_call_blocking(func, *args, **kwargs):
        kwargs.pop("semaphore", None)
        return func(*args, **kwargs)

    monkeypatch.setattr(
        statistic,
        "call_blocking",
        fake_call_blocking,
    )
    monkeypatch.setattr(
        statistic,
        "get_sector_rankings",
        lambda: {"top_sectors": [{"name": "AI"}], "bottom_sectors": [{"name": "地产"}]},
    )
    monkeypatch.setattr(
        statistic,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(
            fetch_market_pct_distribution=lambda date: {"fenbu": [{"1": 2}, {"-1": 3}, {"0": 1}]},
            fetch_market_limit_up_pool=lambda date: ([{"name": "涨停股"}], 5),
            fetch_market_limit_down_pool=lambda date: ([{"name": "跌停股"}], 4),
        ),
    )

    result = asyncio.run(statistic.get_market_statistics("2026-05-25"))

    assert result.source == "sector-rankings"
    assert result.top_sectors == [{"name": "AI"}]
    assert result.bottom_sectors == [{"name": "地产"}]
    assert result.up_count == 2
    assert result.down_count == 3
    assert result.flat_count == 1
    assert result.total_stocks == 6
    assert result.limit_up_count == 5
    assert result.limit_down_count == 4
    assert result.limit_up_stocks == [{"name": "涨停股"}]
    assert result.limit_down_stocks == [{"name": "跌停股"}]
