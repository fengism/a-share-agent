"""巨潮资讯公告源：字段映射、交易所参数与新浪兜底链。"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.financial_data.stock.insights import bulletins
from app.financial_data.stock.insights.sources import (
    CNINFO_ANNOUNCEMENT_QUERY_API,
    CNINFO_BULLETIN_SOURCE_ID,
)
from app.infrastructure.providers import cninfo as cninfo_module


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def _patch_post(monkeypatch: pytest.MonkeyPatch, payload: dict) -> dict:
    captured: dict = {}

    def fake_post(url, *, data=None, headers=None, timeout=None):  # noqa: ANN001
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        return _FakeResponse(json.dumps(payload))

    monkeypatch.setattr(cninfo_module, "provider_post", fake_post)
    return captured


def test_fetch_stock_bulletins_maps_cninfo_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_post(monkeypatch, {
        "totalRecordNum": 42,
        "announcements": [
            {
                "announcementId": "1221234567",
                "secCode": "600519",
                "secName": "贵州茅台",
                "announcementTitle": "2025年年度报告",
                "announcementTime": 1743436800000,  # 2025-04-01 00:00 北京时间
                "adjunctType": "PDF",
                "adjunctUrl": "finalpage/2025-04-01/1221234567.PDF",
                "adjunctSize": 1024,
            }
        ],
    })

    result = cninfo_module.CninfoDataProvider().fetch_stock_bulletins("600519", page=1, page_size=10)

    assert captured["url"] == cninfo_module.CNINFO_ANNOUNCEMENT_QUERY_URL
    assert captured["data"]["column"] == "sse"
    assert captured["data"]["stock"] == "600519,orgId,gssh600519"
    assert captured["data"]["pageSize"] == 10

    assert result["code"] == "600519"
    assert result["name"] == "贵州茅台"
    assert result["total_pages"] == 5  # ceil(42 / 10)

    item = result["items"][0]
    assert item["id"] == "1221234567"
    assert item["title"] == "2025年年度报告"
    assert item["date"] == "2025-04-01"
    assert item["type"] == "PDF"
    assert item["pdf_url"] == "https://static.cninfo.com.cn/finalpage/2025-04-01/1221234567.PDF"
    assert "announcementId=1221234567" in item["url"]
    assert item["origin"] == "巨潮资讯网"


@pytest.mark.parametrize(
    ("code", "column", "org_id"),
    [
        ("600519", "sse", "gssh600519"),
        ("000858", "szse", "gssz000858"),
        ("830799", "bjse", "gsbj830799"),
    ],
)
def test_fetch_stock_bulletins_derives_exchange(
    monkeypatch: pytest.MonkeyPatch, code: str, column: str, org_id: str
) -> None:
    captured = _patch_post(monkeypatch, {"totalRecordNum": 0, "announcements": []})
    cninfo_module.CninfoDataProvider().fetch_stock_bulletins(code, page=2, page_size=30)
    assert captured["data"]["column"] == column
    assert captured["data"]["stock"] == f"{code},orgId,{org_id}"
    assert captured["data"]["pageNum"] == 2


def test_fetch_stock_bulletins_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url, *, data=None, headers=None, timeout=None):  # noqa: ANN001
        return _FakeResponse("<html>blocked</html>")

    monkeypatch.setattr(cninfo_module, "provider_post", fake_post)
    with pytest.raises(RuntimeError):
        cninfo_module.CninfoDataProvider().fetch_stock_bulletins("600519")


class _FakeGateway:
    def __init__(self, outcomes: dict) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    async def call_blocking(self, provider, operation, func, *args, **kwargs):  # noqa: ANN001
        self.calls.append(provider)
        outcome = self.outcomes[provider]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeProvider:
    def fetch_stock_bulletins(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("provider method must be intercepted by the fake gateway")


async def _run_chain(
    monkeypatch: pytest.MonkeyPatch, outcomes: dict
) -> tuple[dict, bulletins._BulletinSource, _FakeGateway]:
    gateway = _FakeGateway(outcomes)
    monkeypatch.setattr(bulletins, "provider_gateway", gateway)
    monkeypatch.setattr(bulletins, "get_provider", lambda name: _FakeProvider())
    raw, source = await bulletins._fetch_bulletin_page("600519", 1, 10)
    return raw, source, gateway


async def test_source_chain_prefers_cninfo(monkeypatch: pytest.MonkeyPatch) -> None:
    raw, source, gateway = await _run_chain(monkeypatch, {
        "cninfo": {"items": [{"id": "1"}], "name": "贵州茅台", "total_pages": 2},
        "sina": {"items": [{"id": "2"}], "name": "贵州茅台", "total_pages": 3},
    })
    assert source.provider == "cninfo"
    assert gateway.calls == ["cninfo"]
    assert raw["items"][0]["id"] == "1"


async def test_source_chain_falls_back_to_sina_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    raw, source, gateway = await _run_chain(monkeypatch, {
        "cninfo": RuntimeError("cninfo down"),
        "sina": {"items": [{"id": "9"}], "name": "贵州茅台", "total_pages": 1},
    })
    assert source.provider == "sina"
    assert gateway.calls == ["cninfo", "sina"]
    assert raw["items"][0]["id"] == "9"


async def test_source_chain_falls_back_when_cninfo_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    raw, source, _ = await _run_chain(monkeypatch, {
        "cninfo": {"items": [], "name": "", "total_pages": 0},
        "sina": {"items": [{"id": "7"}], "name": "贵州茅台", "total_pages": 1},
    })
    assert source.provider == "sina"
    assert raw["items"][0]["id"] == "7"


def test_build_bulletin_page_stamps_source() -> None:
    source = bulletins._BulletinSource(
        provider="cninfo",
        operation="stock_bulletins",
        method="fetch_stock_bulletins",
        source_id=CNINFO_BULLETIN_SOURCE_ID,
        source_api=CNINFO_ANNOUNCEMENT_QUERY_API,
        semaphore=asyncio.Semaphore(1),
    )
    page = bulletins._build_bulletin_page(
        "600519",
        {"name": "贵州茅台", "total_pages": 1, "items": [{"id": "1", "title": "公告", "date": "2025-04-01"}]},
        page=1,
        page_size=10,
        source=source,
    )
    assert page.source == CNINFO_BULLETIN_SOURCE_ID
    assert page.items[0].source == CNINFO_BULLETIN_SOURCE_ID
    assert page.items[0].source_api == CNINFO_ANNOUNCEMENT_QUERY_API
