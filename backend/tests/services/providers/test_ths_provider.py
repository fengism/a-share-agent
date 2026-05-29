from app.services.providers import ths


def test_fetch_stock_forecast_reports_returns_empty_when_no_tables(monkeypatch):
    provider = ths.ThsDataProvider()

    class FakeResp:
        status_code = 200
        text = "<html><body></body></html>"
        encoding = "utf-8"
        def raise_for_status(self):
            pass

    monkeypatch.setattr(ths.requests, "get", lambda *a, **kw: FakeResp())
    df = provider.fetch_stock_forecast_reports("600519")
    assert df.empty
