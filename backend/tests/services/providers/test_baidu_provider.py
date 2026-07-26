from app.constants.http import BD_HEADERS_WITH_COOKIE
from app.services.providers import baidu


def test_get_cookie_headers_uses_custom_token_without_mutating_shared_headers(monkeypatch):
    """Custom cookie should be applied on a copied headers dict."""

    class FakeSettings:
        baidu_cookie = "custom-token"
        baidu_acs_token = ""

    assert "cookie" not in BD_HEADERS_WITH_COOKIE
    monkeypatch.setattr(baidu, "get_settings", lambda: FakeSettings())

    provider = baidu.BaiduDataProvider()
    headers = provider._get_cookie_headers()

    assert headers["cookie"] == "custom-token"
    assert headers is not BD_HEADERS_WITH_COOKIE
    assert "cookie" not in BD_HEADERS_WITH_COOKIE
