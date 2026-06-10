from app.services.providers import twitter


def test_get_session_refreshes_trust_env(monkeypatch):
    """_get_session should reflect the latest http_trust_env runtime setting."""

    class FakeSettings:
        http_trust_env = True
        twitter_feeds = []

    provider = twitter.TwitterDataProvider()
    provider._session.trust_env = False
    monkeypatch.setattr(twitter, "get_settings", lambda: FakeSettings())

    session = provider._get_session()

    assert session.trust_env is True


def test_fetch_article_by_id_returns_empty_dict_on_request_error(monkeypatch):
    """fetch_article_by_id should degrade to an empty dict when request parsing fails."""
    provider = twitter.TwitterDataProvider()

    monkeypatch.setattr(provider, "_request_json", lambda *args, **kwargs: {})

    assert provider.fetch_article_by_id("123") == {}


def test_fetch_user_articles_falls_back_to_preview_text(monkeypatch):
    """fetch_user_articles should use preview_text when article content is empty."""

    class FakeSettings:
        http_trust_env = False
        twitter_feeds = ["tester"]

    monkeypatch.setattr(twitter, "get_settings", lambda: FakeSettings())
    provider = twitter.TwitterDataProvider()

    monkeypatch.setattr(
        provider,
        "_fetch_posts",
        lambda *args, **kwargs: [
            {
                "id": "1",
                "url": "https://x.com/tester/status/1",
                "created_timestamp": 1710000000,
                "article": {
                    "title": "",
                    "preview_text": "preview body",
                },
            }
        ],
    )
    monkeypatch.setattr(
        provider,
        "fetch_article_by_id",
        lambda _: {"id": "1", "url": "https://x.com/tester/status/1", "content": ""},
    )

    items = provider.fetch_user_articles()

    assert len(items) == 1
    assert items[0].content == "preview body"
    assert items[0].title == "preview body"
    assert items[0].author == "tester"
