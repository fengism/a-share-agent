from app.services.providers import cls
from app.services.providers.cls import ClsDataProvider


class DummyResponse:
    def __init__(self, payload=None, text=""):
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_fetch_telegraph_parses_roll_data(monkeypatch):
    captured = {}

    def fake_get(url, headers, timeout, **kwargs):
        captured.update({"url": url, "headers": headers, "timeout": timeout})
        return DummyResponse(payload={
            "data": {
                "roll_data": [
                    {
                        "title": "贵州茅台公告",
                        "content": "贵州茅台600519业绩增长",
                        "shareurl": "https://example.com/news/1",
                        "ctime": 1771948800,
                        "author": "财联社",
                        "read_count": 12,
                        "comment_count": 3,
                    }
                ]
            }
        })

    monkeypatch.setattr(cls.http_client, "get", fake_get)

    result = ClsDataProvider()._fetch_telegraph(code="600519", code_name="贵州茅台")

    assert len(result) == 1
    assert result[0].title == "贵州茅台公告"
    assert result[0].content == "贵州茅台600519业绩增长"
    assert result[0].url == "https://example.com/news/1"
    assert captured["timeout"] == 10


def test_fetch_news_parses_text_json_depth_list(monkeypatch):
    def fake_get(*args, **kwargs):
        return DummyResponse(text='{"data": {"depth_list": [{"title": "市场新闻", "brief": "贵州茅台600519相关", "source": "财联社", "ctime": 1771948800, "external_link": "https://example.com/news/2"}]}}')

    monkeypatch.setattr(cls.http_client, "get", fake_get)

    result = ClsDataProvider()._fetch_news(code="600519", code_name="贵州茅台")

    assert len(result) == 1
    assert result[0].title == "市场新闻"
    assert result[0].content == "贵州茅台600519相关"
    assert result[0].source == "财联社"
    assert result[0].url == "https://example.com/news/2"


def test_cls_empty_data_returns_empty_list(monkeypatch):
    monkeypatch.setattr(cls.http_client, "get", lambda *args, **kwargs: DummyResponse(payload={"data": {}}, text='{"data": {}}'))

    provider = ClsDataProvider()

    assert provider._fetch_telegraph() == []
    assert provider._fetch_news() == []
