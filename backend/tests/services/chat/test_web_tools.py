"""web_tools 的 URL 安全校验、X/Twitter 识别与 tweet URL 解析测试。"""

import pytest

from app.services.chat.tools import web_tools
from app.utils.url_utils import (
    UnsafeUrlError,
    assert_url_safe,
    is_twitter_url,
    parse_tweet_url,
)

# 向后兼容别名
_assert_url_safe = assert_url_safe


class TestAssertUrlSafe:
    def test_rejects_non_http_scheme(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("file:///etc/passwd")
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("ftp://example.com/x")

    def test_rejects_missing_host(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://")

    def test_rejects_loopback(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://127.0.0.1/admin")
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://localhost:8000/")

    def test_rejects_private_ip(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://192.168.1.1/")
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://10.0.0.5/")

    def test_rejects_cloud_metadata(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://169.254.169.254/latest/meta-data/")

    def test_allows_public_ip(self):
        # 公网 IP 直接通过（无需 DNS），不应抛异常
        assert_url_safe("http://1.1.1.1/")

    def test_unresolvable_host_raises(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://no-such-host.invalid/")


class TestIsTwitterUrl:
    def test_matches_x_com(self):
        assert is_twitter_url("https://x.com/elonmusk/status/123")

    def test_matches_twitter_com(self):
        assert is_twitter_url("https://twitter.com/elonmusk/status/123")

    def test_matches_subdomain(self):
        assert is_twitter_url("https://mobile.twitter.com/a/status/1")

    def test_rejects_lookalike_host(self):
        # 旧实现用 url.find("twitter") 会误判，这里必须按主机名判断
        assert not is_twitter_url("https://example.com/twitter-news")
        assert not is_twitter_url("https://nottwitter.example.com/x")

    def test_rejects_plain_news_url(self):
        assert not is_twitter_url("https://finance.sina.com.cn/abc")


class TestParseTweetUrl:
    def test_parse_x_com(self):
        user, tid = parse_tweet_url("https://x.com/jack/status/20")
        assert user == "jack"
        assert tid == "20"

    def test_parse_twitter_com(self):
        user, tid = parse_tweet_url("https://twitter.com/jack/status/99")
        assert user == "jack"
        assert tid == "99"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_tweet_url("https://x.com/jack")


class TestFetchUrlRoutesUnsafe:
    async def test_fetch_url_returns_error_for_private(self):
        result = await web_tools._fetch_url("http://127.0.0.1/secret")
        assert result.get("error")
        assert result["url"] == "http://127.0.0.1/secret"
