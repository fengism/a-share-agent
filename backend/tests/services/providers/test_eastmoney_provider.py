import pandas as pd

from app.constants import EASTMONEY_CLIST_URL, EASTMONEY_STOCK_KLINE_URL
from app.services.providers import eastmoney


class DummyResponse:
    def __init__(self, payload, text=None, status_code=200):
        """Store the JSON payload and optional text body for the mock response.

        Param:
            payload: JSON-serialisable dict returned by json().
            text: raw response body; defaults to empty string when omitted.
        Return:
            None
        """
        self._payload = payload
        self.text = text or ""
        self.status_code = status_code

    def json(self):
        """Return the pre-stored JSON payload.

        Return:
            the payload dict passed during construction.
        """
        return self._payload

    def raise_for_status(self):
        """No-op stand-in for requests.Response.raise_for_status in tests.

        Return:
            None
        """
        return None


def test_fetch_index_kline_parses_klines(monkeypatch):
    """fetch_index_kline parses kline rows into a DataFrame with the right columns."""
    provider = eastmoney.EastMoneyDataProvider()
    captured = {}

    def fake_get(url, **kwargs):
        captured.update({"url": url, "kwargs": kwargs})
        return DummyResponse({
            "data": {
                "code": "000001",
                "klines": ["2026-05-25,3000,3010,3020,2990,100,200,1.2,0.3,9,0.5"],
            }
        })

    monkeypatch.setattr(provider, "em_get_response", fake_get)

    df = provider.fetch_index_kline("000001", "daily", "20260501", "20260525")

    assert isinstance(df, pd.DataFrame)
    assert df.iloc[0]["date"] == "2026-05-25"
    assert df.iloc[0]["close"] == "3010"
    assert captured["url"] == EASTMONEY_STOCK_KLINE_URL
    assert captured["kwargs"]["params"]["secid"] == "1.000001"


def test_fetch_index_kline_empty_klines_returns_empty_df(monkeypatch):
    """fetch_index_kline returns an empty DataFrame when the API yields no klines."""
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(provider, "em_get_response", lambda *args, **kwargs: DummyResponse({"data": {"code": "000001", "klines": []}}))

    df = provider.fetch_index_kline("000001", "daily", "20260501", "20260525")

    assert df.empty


def test_fetch_clist_diff_paginates_and_stops_by_total(monkeypatch):
    """_fetch_clist_diff paginates through pages until the total count is reached."""
    provider = eastmoney.EastMoneyDataProvider()
    captured: list[dict[str, str]] = []

    def fake_get(url, **kwargs):
        params = kwargs.get("params") or {}
        captured.append(params)
        page = int(params.get("pn", "1"))
        if page == 1:
            return DummyResponse({"data": {"diff": [{"f12": "BK1"}], "total": 2}})
        return DummyResponse({"data": {"diff": [{"f12": "BK2"}], "total": 2}})

    monkeypatch.setattr(provider, "em_get_response", fake_get)

    result = provider._fetch_clist_diff({"fields": "f12"}, page_size=1)

    assert result == [{"f12": "BK1"}, {"f12": "BK2"}]
    assert [req["pn"] for req in captured] == ["1", "2"]
    assert [req["pz"] for req in captured] == ["1", "1"]


def test_fetch_clist_diff_returns_empty_on_request_error(monkeypatch):
    """_fetch_clist_diff returns an empty list when the underlying HTTP call fails."""
    provider = eastmoney.EastMoneyDataProvider()
    requested_urls: list[str] = []

    def fake_get(url, **kwargs):
        requested_urls.append(url)
        raise RuntimeError("temporary failure")

    monkeypatch.setattr(provider, "em_get_response", fake_get)

    result = provider._fetch_clist_diff({"fields": "f12"}, page_size=200)

    assert result == []
    assert requested_urls == [EASTMONEY_CLIST_URL]


def test_fetch_industry_boards_maps_columns(monkeypatch):
    """fetch_industry_boards maps raw fields to Chinese column names."""
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(provider, "_fetch_clist_diff", lambda params, page_size: [{"f12": "BK001", "f14": "白酒"}])

    df = provider.fetch_industry_boards()

    assert list(df.columns) == ["板块代码", "板块名称"]
    assert df.iloc[0].to_dict() == {"板块代码": "BK001", "板块名称": "白酒"}


def test_fetch_industry_components_maps_columns(monkeypatch):
    """fetch_industry_components maps raw fields and builds the correct fs filter."""
    provider = eastmoney.EastMoneyDataProvider()
    captured = {}

    def fake_fetch(params, page_size):
        captured.update(params)
        return [{"f12": "600519", "f14": "贵州茅台"}]

    monkeypatch.setattr(provider, "_fetch_clist_diff", fake_fetch)

    df = provider.fetch_industry_components("BK001")

    assert list(df.columns) == ["代码", "名称"]
    assert df.iloc[0].to_dict() == {"代码": "600519", "名称": "贵州茅台"}
    assert captured["fs"] == "b:BK001 f:!50"


def test_build_industry_mapping_normalizes_stock_codes(monkeypatch):
    """build_industry_mapping normalises short codes and drops invalid entries."""
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(
        provider,
        "fetch_industry_boards",
        lambda: pd.DataFrame([{"板块代码": "BK001", "板块名称": "白酒"}]),
    )
    monkeypatch.setattr(
        provider,
        "fetch_industry_components",
        lambda board_code: pd.DataFrame([{"代码": "858"}, {"代码": "600519"}, {"代码": "abc"}]),
    )

    mapping, industry_list = provider.build_industry_mapping()

    assert mapping == {"000858": "白酒", "600519": "白酒"}
    assert industry_list == ["白酒"]


def test_fetch_spot_snapshot_maps_columns_and_units(monkeypatch):
    """fetch_spot_snapshot maps spot fields to Chinese column names."""
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(
        provider,
        "_fetch_clist_diff",
        lambda params, page_size: [
            {
                "f12": "600519",
                "f14": "贵州茅台",
                "f2": "1000",
                "f3": "1.2",
                "f5": "10",
                "f20": "200000000000",
            }
        ],
    )

    df = provider.fetch_spot_snapshot()

    assert df.iloc[0]["代码"] == "600519"
    assert df.iloc[0]["名称"] == "贵州茅台"
    assert df.iloc[0]["成交量"] == 1000
    assert df.iloc[0]["总市值"] == "200000000000"


def test_fetch_market_limit_up_pool_parses_jsonp(monkeypatch):
    """fetch_market_limit_up_pool parses JSONP responses and returns pool + total count."""
    provider = eastmoney.EastMoneyDataProvider()
    captured = {}

    def fake_get(url, *, params, headers, timeout):
        captured.update({"url": url, "params": params, "timeout": timeout})
        return DummyResponse({}, text='callback({"data":{"pool":[{"name":"涨停股"}],"tc":7}})')

    monkeypatch.setattr(provider.em_session, "get", fake_get)

    pool, count = provider.fetch_market_limit_up_pool("2026-05-25")

    assert pool == [{"name": "涨停股"}]
    assert count == 7
    assert captured["params"]["date"] == "20260525"
    assert captured["timeout"] == 15


def test_fetch_market_limit_down_pool_parses_jsonp(monkeypatch):
    """fetch_market_limit_down_pool parses JSONP responses for the limit-down pool."""
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(
        provider.em_session,
        "get",
        lambda *args, **kwargs: DummyResponse({}, text='callback({"data":{"pool":[{"name":"跌停股"}],"tc":3}})'),
    )

    pool, count = provider.fetch_market_limit_down_pool("20260525")

    assert pool == [{"name": "跌停股"}]
    assert count == 3


def test_fetch_market_pct_distribution_parses_jsonp(monkeypatch):
    """fetch_market_pct_distribution parses JSONP responses and returns the fenbu payload."""
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(
        provider.em_session,
        "get",
        lambda *args, **kwargs: DummyResponse({}, text='callback({"data":{"fenbu":[{"1":2}]}})'),
    )

    result = provider.fetch_market_pct_distribution("20260525")

    assert result == {"fenbu": [{"1": 2}]}
