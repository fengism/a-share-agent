import pandas as pd
import pytest

from app.services.providers import eastmoney


class DummyResponse:
    def __init__(self, payload, text=None):
        self._payload = payload
        self.text = text or ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def test_fetch_index_kline_direct_parses_klines(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()
    captured = {}

    def fake_post(url, params, headers, timeout):
        captured.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return DummyResponse({
            "data": {
                "code": "000001",
                "klines": ["2026-05-25,3000,3010,3020,2990,100,200,1.2,0.3,9,0.5"],
            }
        })

    monkeypatch.setattr(eastmoney.http_client, "post", fake_post)

    df = provider.fetch_index_kline_direct("000001", "daily", "20260501", "20260525")

    assert isinstance(df, pd.DataFrame)
    assert df.iloc[0]["日期"] == "2026-05-25"
    assert df.iloc[0]["收盘"] == "3010"
    assert captured["url"] == eastmoney.EASTMONEY_STOCK_KLINE_URL
    assert captured["params"]["secid"] == "1.000001"
    assert captured["timeout"] == 10


def test_fetch_index_kline_direct_empty_klines_returns_empty_df(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(
        eastmoney.http_client,
        "post",
        lambda *args, **kwargs: DummyResponse({"data": {"code": "000001", "klines": []}}),
    )

    df = provider.fetch_index_kline_direct("000001", "daily", "20260501", "20260525")

    assert df.empty


def test_fetch_clist_diff_paginates_and_stops_by_total(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()
    requests: list[dict[str, str]] = []

    def fake_get(url, *, params, headers, timeout):
        requests.append(params)
        page = int(params["pn"])
        if page == 1:
            return DummyResponse({"data": {"diff": [{"f12": "BK1"}], "total": 2}})
        return DummyResponse({"data": {"diff": [{"f12": "BK2"}], "total": 2}})

    monkeypatch.setattr(eastmoney.http_client, "get", fake_get)

    result = provider._fetch_clist_diff({"fields": "f12"}, page_size=1)

    assert result == [{"f12": "BK1"}, {"f12": "BK2"}]
    assert [request["pn"] for request in requests] == ["1", "2"]
    assert [request["pz"] for request in requests] == ["1", "1"]


def test_fetch_clist_diff_raises_request_error(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()
    requested_urls: list[str] = []

    def fake_get(url, *, params, headers, timeout):
        requested_urls.append(url)
        raise RuntimeError("temporary failure")

    monkeypatch.setattr(eastmoney.http_client, "get", fake_get)

    with pytest.raises(RuntimeError, match="temporary failure"):
        provider._fetch_clist_diff({"fields": "f12"}, page_size=200)

    assert requested_urls == [eastmoney.EASTMONEY_CLIST_URL]


def test_fetch_industry_boards_direct_maps_columns(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(provider, "_fetch_clist_diff", lambda params, page_size: [{"f12": "BK001", "f14": "白酒"}])

    df = provider.fetch_industry_boards_direct()

    assert list(df.columns) == ["板块代码", "板块名称"]
    assert df.iloc[0].to_dict() == {"板块代码": "BK001", "板块名称": "白酒"}


def test_fetch_industry_components_direct_maps_columns(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()
    captured = {}

    def fake_fetch(params, page_size):
        captured.update(params)
        return [{"f12": "600519", "f14": "贵州茅台"}]

    monkeypatch.setattr(provider, "_fetch_clist_diff", fake_fetch)

    df = provider.fetch_industry_components_direct("BK001")

    assert list(df.columns) == ["代码", "名称"]
    assert df.iloc[0].to_dict() == {"代码": "600519", "名称": "贵州茅台"}
    assert captured["fs"] == "b:BK001 f:!50"


def test_build_industry_mapping_direct_normalizes_stock_codes(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(
        provider,
        "fetch_industry_boards_direct",
        lambda: pd.DataFrame([{"板块代码": "BK001", "板块名称": "白酒"}]),
    )
    monkeypatch.setattr(
        provider,
        "fetch_industry_components_direct",
        lambda board_code: pd.DataFrame([{"代码": "858"}, {"代码": "600519"}, {"代码": "abc"}]),
    )

    mapping, industry_list = provider.build_industry_mapping_direct()

    assert mapping == {"000858": "白酒", "600519": "白酒"}
    assert industry_list == ["白酒"]


def test_fetch_spot_snapshot_direct_maps_columns_and_units(monkeypatch):
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

    df = provider.fetch_spot_snapshot_direct()

    assert df.iloc[0]["代码"] == "600519"
    assert df.iloc[0]["名称"] == "贵州茅台"
    assert df.iloc[0]["成交量"] == 1000
    assert df.iloc[0]["总市值"] == "200000000000"


def test_fetch_market_limit_up_pool_parses_jsonp(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()
    captured = {}

    def fake_get(url, *, params, headers, timeout):
        captured.update({"url": url, "params": params, "timeout": timeout})
        return DummyResponse({}, text='callback({"data":{"pool":[{"name":"涨停股"}],"tc":7}})')

    monkeypatch.setattr(eastmoney.requests, "get", fake_get)

    pool, count = provider.fetch_market_limit_up_pool("2026-05-25")

    assert pool == [{"name": "涨停股"}]
    assert count == 7
    assert captured["params"]["date"] == "20260525"
    assert captured["timeout"] == 15


def test_fetch_market_limit_down_pool_parses_jsonp(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(
        eastmoney.requests,
        "get",
        lambda *args, **kwargs: DummyResponse({}, text='callback({"data":{"pool":[{"name":"跌停股"}],"tc":3}})'),
    )

    pool, count = provider.fetch_market_limit_down_pool("20260525")

    assert pool == [{"name": "跌停股"}]
    assert count == 3


def test_fetch_market_pct_distribution_parses_jsonp(monkeypatch):
    provider = eastmoney.EastMoneyDataProvider()

    monkeypatch.setattr(
        eastmoney.requests,
        "get",
        lambda *args, **kwargs: DummyResponse({}, text='callback({"data":{"fenbu":[{"1":2}]}})'),
    )

    result = provider.fetch_market_pct_distribution("20260525")

    assert result == {"fenbu": [{"1": 2}]}
