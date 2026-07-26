import json

import requests

from app.services.providers import sina


class DummyResponse:
    def __init__(self, records, status_code=200):
        """Serialise the records list as the response body and store the status code.

        Args:
            records: JSON-serialisable list used as the response payload.
            status_code: HTTP status to expose; defaults to 200.
        Return:
            None
        """
        self.text = json.dumps(records, ensure_ascii=False)
        self.status_code = status_code


def test_fetch_spot_snapshot_direct_maps_columns_and_units(monkeypatch):
    """fetch_spot_snapshot_direct maps Sina fields to Chinese columns and yuan values."""
    provider = sina.SinaDataProvider()
    calls = []

    def fake_get(self, url, *, params, timeout):
        calls.append(params)
        if params["page"] == 1:
            return DummyResponse([
                {
                    "code": "600519",
                    "name": "贵州茅台",
                    "trade": "1000",
                    "volume": "10",
                    "mktcap": "200",
                    "nmc": "150",
                }
            ])
        return DummyResponse([])

    monkeypatch.setattr(requests.Session, "get", fake_get)

    df = provider.fetch_spot_snapshot()

    assert df.iloc[0]["代码"] == "600519"
    assert df.iloc[0]["名称"] == "贵州茅台"
    assert df.iloc[0]["成交量"] == 1000
    assert df.iloc[0]["总市值"] == 2_000_000
    assert df.iloc[0]["流通市值"] == 1_500_000
    assert [call["page"] for call in calls] == [1]
