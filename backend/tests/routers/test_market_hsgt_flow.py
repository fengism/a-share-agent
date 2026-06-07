from fastapi.testclient import TestClient

from app.main import app
from app.routers import market


client = TestClient(app)


def test_get_hsgt_flow_route(monkeypatch):
    """Test GET /api/market/hsgt-flow returns the service payload."""
    async def fake_get_hsgt_flow():
        return {
            "updated_at": "2026-05-27 14:35:00",
            "unit": "亿元",
            "points": [{"time": "09:30", "hgt": 1.0, "sgt": 2.0, "total": 3.0}],
        }

    monkeypatch.setattr(market, "get_hsgt_flow_service", fake_get_hsgt_flow)

    response = client.get("/api/market/hsgt-flow")

    assert response.status_code == 200
    assert response.json()["points"][0]["total"] == 3.0
