from app.services.providers import cls
from app.services.providers.cls import ClsDataProvider


class DummyResponse:
    def __init__(self, payload=None, text=""):
        """Store the JSON payload and raw text for the mock response.

        Param:
            payload: JSON-serialisable dict returned by json(); defaults to {}.
            text: raw response body returned by .text; defaults to empty string.
        Return:
            None
        """
        self._payload = payload or {}
        self.text = text

    def json(self):
        """Return the pre-stored JSON payload.

        Return:
            the payload dict passed during construction.
        """
        return self._payload


def test_fetch_market_news_parses_text_json_depth_list(monkeypatch):
    """ClsDataProvider.fetch_market_news parses depth_list items from a text/json body."""
    def fake_get(*args, **kwargs):
        return DummyResponse(text='{"data": {"depth_list": [{"title": "市场新闻", "brief": "贵州茅台600519相关", "source": "财联社", "ctime": 1771948800, "external_link": "https://example.com/news/2"}]}}')

    monkeypatch.setattr(cls.http_client, "get", fake_get)

    result = ClsDataProvider().fetch_market_news(code="600519", code_name="贵州茅台")

    assert len(result) == 1
    assert result[0].title == "市场新闻"
    assert result[0].content == "贵州茅台600519相关"
    assert result[0].source == "财联社"
    assert result[0].url == "https://example.com/news/2"


def test_cls_empty_data_returns_empty_list(monkeypatch):
    """ClsDataProvider.fetch_market_news returns an empty list when data is empty."""
    monkeypatch.setattr(cls.http_client, "get", lambda *args, **kwargs: DummyResponse(payload={"data": {}}, text='{"data": {}}'))

    provider = ClsDataProvider()

    assert provider.fetch_market_news() == []
