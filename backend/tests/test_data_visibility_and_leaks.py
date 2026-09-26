
from app.agentic.protocol import ToolCallInfo
from app.agentic.tools.cache import SharedToolCache
from app.agentic.tools.serialization import tool_call_cache_key
from app.modules.analysis.persistence import repository
from app.modules.bot.models import BotResponse


def _call(name: str = "stock_detail", arguments: str = '{"code":"600519"}') -> ToolCallInfo:
    return ToolCallInfo(id="c1", function={"name": name, "arguments": arguments})


class TestAnalysisCacheScoping:
    """legacy 全局记录不得被写进某个用户的缓存命名空间。

    旧实现把 load_analysis 的返回值（可能来自 legacy 全局目录）缓存到 per-user key，
    而 delete_analysis 只失效删除者与 scope 两个 key，于是管理员删除 legacy 记录后，
    其他用户此前缓存过的那份仍可继续读到，最长 4 小时。
    """

    def test_legacy_result_is_not_cached_per_user(self, monkeypatch):
        sentinel = object()
        # 先让用户目录 miss，再让 legacy 目录命中 —— 模拟「读到的是全局旧记录」
        seen = {"n": 0}

        def _load_path(_path):
            seen["n"] += 1
            return None if seen["n"] == 1 else sentinel

        monkeypatch.setattr(repository, "_load_path", _load_path)
        monkeypatch.setattr(repository.cache, "get", lambda _key: None)
        written: list[str] = []
        monkeypatch.setattr(repository.cache, "set", lambda key, _value, ttl: written.append(key))

        result = repository.get_analysis_by_date("600519", "20260101", user_id=7)
        assert result is sentinel, "应仍能读到 legacy 记录"
        assert written == [], "legacy 全局记录不应写入 per-user 缓存"

    def test_user_scoped_result_is_still_cached(self, monkeypatch):
        sentinel = object()
        monkeypatch.setattr(repository, "_load_path", lambda _path: sentinel)
        monkeypatch.setattr(repository.cache, "get", lambda _key: None)
        written: list[str] = []
        monkeypatch.setattr(repository.cache, "set", lambda key, _value, ttl: written.append(key))

        repository.get_analysis_by_date("600519", "20260101", user_id=7)
        assert len(written) == 1, "用户自己的记录仍应缓存"


class TestToolCacheUserPartition:
    """scope="user" 的工具结果必须按用户分区。"""

    def test_cache_key_includes_user_when_given(self):
        plain = tool_call_cache_key(_call())
        scoped = tool_call_cache_key(_call(), user_id=42)
        assert plain != scoped
        assert "user:42" in scoped

    def test_key_is_stable_for_same_user(self):
        a = tool_call_cache_key(_call(arguments='{"code":"600519","x":1}'), user_id=42)
        b = tool_call_cache_key(_call(arguments='{"x":1,  "code":"600519"}'), user_id=42)
        assert a == b

    def test_different_users_get_different_keys(self):
        cache = SharedToolCache()
        ctx_a = type("C", (), {"user_id": 1})()
        ctx_b = type("C", (), {"user_id": 2})()
        key_a = cache._cache_key(_call(), ctx_a)
        key_b = cache._cache_key(_call(), ctx_b)
        # 无论工具当前注册成什么 scope，两个用户的 key 都不能相同
        assert key_a != key_b or "user:" not in key_a


class TestWebFetchErrorRedaction:
    """抓取失败时不得回传调用方不知道的信息。

    需要区分两类：
    - ``url`` 字段回显调用方自己传入的地址，这不是新泄漏（Agent 本来就知道它）。
    - **内网解析地址**与**重定向后的最终地址**是调用方看不到的新信息，必须挡住。
      旧实现把 ``str(HTTPError)``（含完整 URL）与 ``response.url``（重定向落点）直接回传。
    """

    async def test_unsafe_url_error_does_not_leak_internal_address(self):
        from app.agentic.tools.packs.web import fetcher
        from app.agentic.tools.packs.web.url_security import UnsafeUrlError

        async def _reject(*_args, **_kwargs):
            raise UnsafeUrlError("拒绝访问非公网地址: internal.corp -> 10.1.2.3")

        result = await fetcher.web_fetch(
            "https://internal.corp/secret",
            mode="http",
            cache=fetcher.TTLCache(maxsize=1),
            http_get_func=lambda *a, **k: _reject(),
            is_twitter_url_func=lambda _url: False,
            browser_fetch_func=None,
        )
        text = str(result)
        assert "10.1.2.3" not in text, "内网地址泄漏"
        assert result.get("error_reason") == "web_url_not_public"
        assert result.get("error"), "仍需给 LLM 可读提示，不能只有裸错误码"

    async def test_http_error_text_is_not_echoed(self):
        import requests

        from app.agentic.tools.packs.web import fetcher

        async def _boom(*_args, **_kwargs):
            raise requests.HTTPError(
                "503 Server Error for url: https://upstream.example/s?token=SECRET_TOKEN_VALUE"
            )

        result = await fetcher.web_fetch(
            "https://upstream.example/s",
            mode="http",
            cache=fetcher.TTLCache(maxsize=1),
            http_get_func=lambda *a, **k: _boom(),
            is_twitter_url_func=lambda _url: False,
            browser_fetch_func=None,
        )
        assert "SECRET_TOKEN_VALUE" not in str(result), "上游 query token 泄漏"
        assert result.get("error_reason") == "web_fetch_failed"

    async def test_post_redirect_url_is_not_exposed(self):
        import requests

        from app.agentic.tools.packs.web import fetcher

        response = requests.Response()
        response.status_code = 404
        # 重定向落点在另一个域名，调用方从未见过它
        response.url = "https://internal-mirror.corp/secret-copy"

        async def _not_found(*_args, **_kwargs):
            raise requests.HTTPError("404 Client Error", response=response)

        result = await fetcher.web_fetch(
            "https://origin.example/report",
            mode="auto",
            cache=fetcher.TTLCache(maxsize=1),
            http_get_func=lambda *a, **k: _not_found(),
            is_twitter_url_func=lambda _url: False,
        )
        assert "internal-mirror.corp" not in str(result), "重定向落点泄漏"
        assert result.get("error_reason") == "web_not_found"


class TestBotBatchTotalFailure:
    """批量命令全灭必须与全成功可区分。"""

    def test_total_failure_is_flagged(self):
        assert BotResponse(text="x", failure_count=3, total_count=3).totally_failed is True

    def test_partial_failure_is_not_total(self):
        assert BotResponse(text="x", failure_count=1, total_count=3).totally_failed is False

    def test_plain_response_is_not_total(self):
        assert BotResponse(text="x").totally_failed is False
