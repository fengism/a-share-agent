from app.services.providers import tencent


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload
        import json
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def test_fetch_stock_concept_maps_concepts_and_plates(monkeypatch):
    provider = tencent.TencentDataProvider()
    captured = {}

    def fake_get(url, *, params, headers, timeout):
        captured.update({"params": params, "timeout": timeout})
        return DummyResponse(
            {
                "data": {
                    "concept": [{"id": "C1", "name": "人工智能"}],
                    "plate": [
                        {"level": "1", "code": "P1", "name": "科技"},
                        {"level": "2", "code": "P2", "name": "半导体"},
                    ],
                }
            }
        )

    monkeypatch.setattr(tencent.requests, "get", fake_get)

    result = provider.fetch_stock_concepts("600519")

    assert result is not None
    assert result.concepts[0].name == "人工智能"
    assert result.first_concept.name == "科技"
    assert result.second_concept.name == "半导体"
    assert captured["params"]["code"] == "sh600519"
    assert captured["timeout"] == 5


def test_fetch_market_sector_rankings_direct_maps_top_and_bottom(monkeypatch):
    provider = tencent.TencentDataProvider()
    orders = []

    def fake_get(url, *, params, timeout):
        orders.append(params["o"])
        return DummyResponse(
            {
                "data": [
                    {
                        "bd_name": "AI",
                        "bd_code": "BK001",
                        "bd_zdf": "1.2",
                        "bd_zdf5": "3.4",
                        "bd_zdf20": "5.6",
                        "nzg_name": "龙头股",
                        "nzg_zdf": "7.8",
                    }
                ]
            }
        )

    monkeypatch.setattr(tencent.requests, "get", fake_get)

    top_df, bottom_df = provider.fetch_market_sector_rankings_direct()

    assert top_df.iloc[0]["板块名称"] == "AI"
    assert bottom_df.iloc[0]["领涨跌股票名称"] == "龙头股"
    assert orders == ["0", "1"]
