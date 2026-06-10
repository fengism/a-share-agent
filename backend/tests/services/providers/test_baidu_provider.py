from app.services.providers import baidu


def test_get_cookie_headers_uses_custom_token_without_mutating_shared_headers(monkeypatch):
    """Custom acs-token should be applied on a copied headers dict."""

    class FakeSettings:
        baidu_acs_token = "custom-token"

    original_token = baidu.BD_HEADERS_WITH_COOKIE["acs-token"]
    monkeypatch.setattr(baidu, "get_settings", lambda: FakeSettings())

    provider = baidu.BaiduDataProvider()
    headers = provider._get_cookie_headers()

    assert headers["acs-token"] == "custom-token"
    assert headers is not baidu.BD_HEADERS_WITH_COOKIE
    assert baidu.BD_HEADERS_WITH_COOKIE["acs-token"] == original_token
