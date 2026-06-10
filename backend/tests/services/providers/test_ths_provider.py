from app.services.providers import ths


def test_fetch_stock_forecast_reports_returns_empty_when_no_tables(monkeypatch):
    """fetch_stock_forecast_reports returns an empty DataFrame when no HTML tables are present."""
    provider = ths.ThsDataProvider()

    class FakeResp:
        status_code = 200
        text = "<html><body></body></html>"
        encoding = "utf-8"
        def raise_for_status(self):
            pass

    monkeypatch.setattr(provider._session, "request", lambda *a, **kw: FakeResp())
    df = provider.fetch_stock_forecast_reports("600519")
    assert df.empty


def test_fetch_market_volume_merges_day_and_minute_data(monkeypatch):
    """fetch_market_volume should combine day and minute payloads into MarketVolume."""
    provider = ths.ThsDataProvider()

    monkeypatch.setattr(provider, "fetch_market_volume_day", lambda: {
        "date": "2026-06-10",
        "amount_before_one_day": 1.0,
        "amount_average_60_day": 2.0,
    })
    monkeypatch.setattr(provider, "fetch_market_volume_minute", lambda: {
        "amount": 3.0,
    })

    market_volume = provider.fetch_market_volume()
    assert market_volume.date == "2026-06-10"
    assert market_volume.amount == 3.0
    assert market_volume.amount_before_one_day == 1.0
    assert market_volume.amount_average_60_day == 2.0


def test_get_session_refreshes_trust_env(monkeypatch):
    """_get_session should reflect the latest http_trust_env runtime setting."""
    provider = ths.ThsDataProvider()
    provider._session.trust_env = False

    class FakeSettings:
        http_trust_env = True

    monkeypatch.setattr(ths, "get_settings", lambda: FakeSettings())

    session = provider._get_session()
    assert session.trust_env is True
