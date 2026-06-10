import asyncio
from types import SimpleNamespace

from app.services.market import macro


def test_get_macro_data_uses_eastmoney_provider(monkeypatch):
    """get_macro_data should assemble latest/trend blocks from the EastMoney provider."""
    def fetch_china_cpi():
        return None

    def fetch_china_ppi():
        return None

    def fetch_china_pmi():
        return None

    def fetch_china_economy_currency_supply():
        return None

    monkeypatch.setattr(macro.cache, "get", lambda key: None)
    monkeypatch.setattr(macro.cache, "set", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        macro,
        "_get_eastmoney_provider",
        lambda: SimpleNamespace(
            fetch_china_cpi=fetch_china_cpi,
            fetch_china_ppi=fetch_china_ppi,
            fetch_china_pmi=fetch_china_pmi,
            fetch_china_economy_currency_supply=fetch_china_economy_currency_supply,
        ),
    )

    async def fake_call_blocking(func, *args, **kwargs):
        name = getattr(func, "__name__", "")
        if name == "fetch_china_cpi":
            return [{"TIME": "2026-05", "NATIONAL_SAME": "0.3", "NATIONAL_SEQUENTIAL": "0.1", "NATIONAL_ACCUMULATE": "0.2"}]
        if name == "fetch_china_ppi":
            return [{"TIME": "2026-05", "BASE": "98.0", "BASE_SAME": "-1.0", "BASE_ACCUMULATE": "-0.8"}]
        if name == "fetch_china_pmi":
            return [{"TIME": "2026-05", "MAKE_INDEX": "50.2", "MAKE_SAME": "0.4", "NMAKE_INDEX": "51.1", "NMAKE_SAME": "0.5"}]
        if name == "fetch_china_economy_currency_supply":
            return [{"TIME": "2026-05", "BASIC_CURRENCY": "13", "BASIC_CURRENCY_SAME": "8", "CURRENCY": "70", "CURRENCY_SAME": "5", "FREE_CASH": "310", "FREE_CASH_SAME": "7"}]
        raise AssertionError(name)

    monkeypatch.setattr(macro, "call_blocking", fake_call_blocking)

    result = asyncio.run(macro.get_macro_data())

    assert result["cpi"]["latest"]["TIME"] == "2026-05"
    assert result["ppi"]["latest"]["BASE"] == "98.0"
    assert result["pmi"]["trend"][0]["MAKE_INDEX"] == "50.2"
    assert result["money_supply"]["latest"]["FREE_CASH_SAME"] == "7"
