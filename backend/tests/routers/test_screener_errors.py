from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.models.screener import ScreenerResult
from app.routers import screener


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(screener.router, prefix="/api/screener")
    return TestClient(app)


def test_screen_stocks_returns_400_for_value_error(monkeypatch):
    async def fake_screen_stocks(filters):
        raise ValueError("invalid filter")

    monkeypatch.setattr(screener, "screen_stocks_service", fake_screen_stocks)

    response = build_client().post("/api/screener/screen", json={})

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid filter"}


def test_get_industries_returns_500_for_unexpected_error(monkeypatch):
    async def fake_get_industry_list():
        raise RuntimeError("provider failed")

    monkeypatch.setattr(screener, "get_industry_list", fake_get_industry_list)

    response = build_client().get("/api/screener/industries")

    assert response.status_code == 500
    assert response.json() == {"detail": "获取行业列表失败: provider failed"}


def test_compute_percentiles_preserves_explicit_http_exception():
    response = build_client().post(
        "/api/screener/percentile",
        json={"codes": [f"6005{i:02d}" for i in range(51)]},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "单次最多50只股票"}


def test_compute_percentiles_preserves_service_http_exception(monkeypatch):
    async def fake_compute_percentiles(*, codes, indicator, period):
        raise HTTPException(status_code=409, detail="already running")

    monkeypatch.setattr(screener, "compute_percentiles_service", fake_compute_percentiles)

    response = build_client().post("/api/screener/percentile", json={"codes": ["600519"]})

    assert response.status_code == 409
    assert response.json() == {"detail": "already running"}


def test_screen_stocks_success_path(monkeypatch):
    async def fake_screen_stocks(filters):
        return ScreenerResult(items=[], total=0, page=filters.page, page_size=filters.page_size)

    monkeypatch.setattr(screener, "screen_stocks_service", fake_screen_stocks)

    response = build_client().post("/api/screener/screen", json={"page": 2, "page_size": 20})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 2, "page_size": 20}
