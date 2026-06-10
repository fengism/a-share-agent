import pandas as pd

from app.services.providers import tdx


class FakeClient:
    def __init__(self):
        self.calls = []

    def bars(self, **kwargs):
        self.calls.append(("bars", kwargs))
        df = pd.DataFrame(
            {
                "open": [10, 11],
                "close": [11, 12],
                "high": [12, 13],
                "low": [9, 10],
                "volume": [100, 200],
                "amount": [1000, 2400],
            },
            index=pd.to_datetime(["2026-06-01", "2026-06-02"]),
        )
        df.index.name = "datetime"
        return df

    def index(self, **kwargs):
        self.calls.append(("index", kwargs))
        return pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2026-06-01", "2026-06-02"]),
                "open": [3000, 3010],
                "close": [3010, 3020],
                "high": [3020, 3030],
                "low": [2990, 3000],
                "volume": [10, 20],
                "amount": [100000, 200000],
            }
        )

    def F10(self, symbol, name):
        self.calls.append(("F10", {"symbol": symbol, "name": name}))
        return f"{symbol}-{name}"


def test_tdx_client_is_lazy(monkeypatch):
    """TdxDataProvider does not create a mootdx client until client is accessed."""
    created = []

    def fake_factory(**kwargs):
        created.append(kwargs)
        return FakeClient()

    monkeypatch.setattr(tdx.Quotes, "factory", fake_factory)

    provider = tdx.TdxDataProvider()

    assert created == []
    assert isinstance(provider.client, FakeClient)
    assert provider.client is provider.client
    assert len(created) == 1


def test_fetch_stock_kline_formats_and_filters_rows():
    """fetch_stock_kline normalises mootdx bars output into standard kline columns."""
    provider = tdx.TdxDataProvider()
    provider._client = FakeClient()

    df = provider.fetch_stock_kline("600519", start_date="20260601", end_date="20260602")

    assert list(df.columns) == provider.KLINE_COLUMNS
    assert df["date"].tolist() == ["2026-06-01", "2026-06-02"]
    assert df.iloc[1]["pre_close"] == 11
    assert round(df.iloc[1]["change_pct"], 4) == round((12 - 11) / 11 * 100, 4)
    assert provider.client.calls[0] == (
        "bars",
        {"symbol": "600519", "frequency": provider.DAILY_FREQUENCY, "offset": 2},
    )


def test_fetch_index_kline_keeps_raw_index_symbol_and_scales_volume():
    """fetch_index_kline strips sh/sz prefixes without applying stock exchange classification."""
    provider = tdx.TdxDataProvider()
    provider._client = FakeClient()

    df = provider.fetch_index_kline("sh000001", start_date="2026-06-01", end_date="2026-06-02")

    assert df["volume"].tolist() == [1000, 2000]
    assert provider.client.calls[0] == (
        "index",
        {"symbol": "000001", "frequency": provider.DAILY_FREQUENCY, "start": 0, "offset": 2},
    )


def test_fetch_basic_info_returns_category_mapping():
    """fetch_basic_info returns F10 content instead of printing to stdout."""
    provider = tdx.TdxDataProvider()
    provider._client = FakeClient()

    result = provider.fetch_basic_info("600519")

    assert result["公司概况"] == "600519-公司概况"
    assert provider.client.calls[0][0] == "F10"
