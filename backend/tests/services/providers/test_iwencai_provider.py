import pytest

from app.services.providers.iwencai import IwencaiDataProvider


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {"status_code": 0}
        self.text = text

    def json(self):
        return self._payload


def test_select_stock_uses_shared_query_payload_and_skill_id(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured.update({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return DummyResponse(payload={"status_code": 0, "datas": [{"股票简称": "贵州茅台"}]})

    monkeypatch.setattr("app.services.providers.iwencai.requests.post", fake_post)
    monkeypatch.setattr(
        IwencaiDataProvider,
        "_base_url",
        property(lambda self: "https://example.com"),
    )
    monkeypatch.setattr(
        IwencaiDataProvider,
        "_api_key",
        property(lambda self: "test-key"),
    )
    provider = IwencaiDataProvider()

    result = provider.select_stocks("白酒股", page=2, limit=15, expand_index=False)

    assert result == [{"股票简称": "贵州茅台"}]
    assert captured["url"] == "https://example.com/v1/query2data"
    assert captured["json"] == {
        "query": "白酒股",
        "page": "2",
        "limit": "15",
        "is_cache": "1",
        "expand_index": "false",
    }
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["X-Claw-Skill-Id"] == "hithink-astock-selector"
    assert captured["timeout"] == 30


def test_search_raises_http_error(monkeypatch):
    def fake_post(*args, **kwargs):
        return DummyResponse(status_code=500, text="server error detail")

    monkeypatch.setattr("app.services.providers.iwencai.requests.post", fake_post)
    monkeypatch.setattr(
        IwencaiDataProvider,
        "_base_url",
        property(lambda self: "https://example.com"),
    )
    provider = IwencaiDataProvider()

    with pytest.raises(RuntimeError, match="iwencai HTTP 500"):
        provider.search("人工智能", channel="news", size=3)


def test_query_raises_business_error(monkeypatch):
    def fake_post(*args, **kwargs):
        return DummyResponse(payload={"status_code": 1001, "status_msg": "bad query"})

    monkeypatch.setattr("app.services.providers.iwencai.requests.post", fake_post)
    monkeypatch.setattr(
        IwencaiDataProvider,
        "_base_url",
        property(lambda self: "https://example.com"),
    )
    provider = IwencaiDataProvider()

    with pytest.raises(RuntimeError, match="bad query"):
        provider.query_stock_data("贵州茅台 ROE")
