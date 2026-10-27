"""出网目标校验（SSRF 防护）。

三条线：

1. **始终拦截**：云元数据/链路本地/组播等自建模型永远不会用到的网段，与开关无关；
2. **私网开关**：``llm_allow_private_endpoints`` 决定 127/8、10/8、172.16/12、192.168/16、
   fc00::/7 是否可达（默认允许，否则 docker 里的 ``ollama`` 服务名会被误伤）；
3. **接线**：模型列表探测与 LLM 客户端 spec 都必须真的调用这份策略，且拦截时**不发请求**。

DNS 解析在测试里全部打桩，避免依赖外网或本机 hosts。
"""

from __future__ import annotations

import inspect
import socket

import pytest

from app.configuration.schema import Settings
from app.domain.llm import LLMConfigurationError
from app.infrastructure.http import url_guard
from app.infrastructure.http.url_guard import (
    OutboundUrlBlockedError,
    describe_blocked_target,
    ensure_outbound_url_allowed,
)
from app.infrastructure.llm.spec import resolve_llm_client_spec


def _stub_dns(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> None:
    """把主机名映射到固定 IP；未登记的域名模拟解析失败。"""

    def fake_getaddrinfo(host, *_args, **_kwargs):
        target = mapping.get(str(host))
        if target is None:
            raise socket.gaierror(socket.EAI_NONAME, "stubbed")
        family = socket.AF_INET6 if ":" in target else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (target, 0))]

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", fake_getaddrinfo)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://100.100.100.200/latest/meta-data/",
        "http://[fe80::1]/v1",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://instance-data.ec2.internal/latest/",
    ],
)
@pytest.mark.parametrize("allow_private", [True, False])
def test_metadata_targets_are_always_blocked(url: str, allow_private: bool) -> None:
    assert describe_blocked_target(url, allow_private=allow_private) is not None


@pytest.mark.parametrize(
    "url",
    ["http://10.0.0.5/v1", "http://172.20.0.3:8080/v1", "http://192.168.1.10:8000/v1", "http://[fd00::1]/v1"],
)
def test_lan_targets_require_explicit_opt_in(url: str) -> None:
    """RFC1918/ULA 默认拦截（任意用户可写的 base_url + 内网 = 服务器变探测器）。"""
    assert describe_blocked_target(url, allow_private=True) is None
    reason = describe_blocked_target(url, allow_private=False)
    assert reason is not None and "内网" in reason


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:11434/v1", "http://[::1]:11434/v1", "http://localhost:11434/v1"],
)
@pytest.mark.parametrize("allow_private", [True, False])
def test_loopback_is_always_allowed(url: str, allow_private: bool) -> None:
    """回环是本机自建模型的默认地址（Ollama），与开关无关都放行。"""
    assert describe_blocked_target(url, allow_private=allow_private) is None


@pytest.mark.parametrize(
    "url",
    ["https://api.deepseek.com/v1", "https://open.bigmodel.cn/api/paas/v4"],
)
@pytest.mark.parametrize("allow_private", [True, False])
def test_public_targets_are_allowed(url: str, allow_private: bool) -> None:
    assert describe_blocked_target(url, allow_private=allow_private) is None


@pytest.mark.parametrize("url", ["ftp://example.com", "file:///etc/passwd", "example.com/v1"])
def test_non_http_schemes_are_rejected(url: str) -> None:
    assert describe_blocked_target(url, allow_private=True) is not None


def test_ipv4_mapped_ipv6_is_unwrapped() -> None:
    assert describe_blocked_target("http://[::ffff:169.254.169.254]/", allow_private=True) is not None


def test_obfuscated_forms_are_normalized_before_the_decision() -> None:
    """十进制/八进制/十六进制/带后缀的写法都会先解析成真实 IP 再判定。"""
    # 归一成 127.0.0.1 → 回环，始终允许
    for url in ("http://2130706433:11434/v1", "http://0177.0.0.1:11434/v1", "http://0x7f.1:11434/v1"):
        assert describe_blocked_target(url, allow_private=False) is None
    # 归一成 169.254.169.254 → 元数据，始终拦截（注意 0xa9fea9fe = 169.254.169.254）
    assert describe_blocked_target("http://2852039166/v1", allow_private=True) is not None


def test_dns_name_pointing_at_metadata_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """攻击者用自己的域名 CNAME 到元数据地址时，按解析结果拦截。"""
    _stub_dns(monkeypatch, {"evil.example.com": "169.254.169.254"})
    reason = describe_blocked_target("http://evil.example.com/v1", allow_private=True)
    assert reason is not None and "169.254.169.254" in reason


def test_dns_name_pointing_at_private_ip_follows_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_dns(monkeypatch, {"ollama.internal": "172.18.0.4"})
    assert describe_blocked_target("http://ollama.internal:11434/v1", allow_private=True) is None
    assert describe_blocked_target("http://ollama.internal:11434/v1", allow_private=False) is not None


def test_unresolvable_host_defers_to_the_real_request(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_dns(monkeypatch, {})
    assert describe_blocked_target("http://does-not-exist.invalid/v1", allow_private=False) is None


def test_ensure_raises_with_displayable_reason() -> None:
    with pytest.raises(OutboundUrlBlockedError) as excinfo:
        ensure_outbound_url_allowed("http://169.254.169.254/", allow_private=True)
    assert "元数据" in excinfo.value.reason
    # 放行时不应抛错
    ensure_outbound_url_allowed("https://api.deepseek.com/v1", allow_private=False)


def test_llm_client_spec_rejects_metadata_base_url() -> None:
    settings = Settings(
        llm_provider="custom",
        llm_model="m",
        llm_api_key="k",
        llm_base_url="http://169.254.169.254/v1",
    )
    with pytest.raises(LLMConfigurationError) as excinfo:
        resolve_llm_client_spec(settings)
    assert "出网策略" in str(excinfo.value)


def test_llm_client_spec_allows_local_ollama_by_default() -> None:
    """开箱即用的本地模型：默认配置（开关关闭）下 127.0.0.1 必须可用。"""
    base = Settings(
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        llm_base_url="http://127.0.0.1:11434/v1",
    )
    assert base.llm_allow_private_endpoints is False
    assert resolve_llm_client_spec(base).base_url == "http://127.0.0.1:11434/v1"


def test_llm_client_spec_rejects_lan_address_unless_opted_in() -> None:
    lan = Settings(
        llm_provider="custom",
        llm_model="m",
        llm_api_key="k",
        llm_base_url="http://172.18.0.4:11434/v1",
    )
    with pytest.raises(LLMConfigurationError) as excinfo:
        resolve_llm_client_spec(lan)
    assert "LLM_ALLOW_PRIVATE_ENDPOINTS" in str(excinfo.value)
    opted_in = lan.model_copy(update={"llm_allow_private_endpoints": True})
    assert resolve_llm_client_spec(opted_in).base_url == "http://172.18.0.4:11434/v1"


async def test_models_probe_blocks_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.settings import service as settings_service
    from app.modules.settings.schemas import LlmModelsRequest

    called = {"http": 0}

    def fake_http_get():
        called["http"] += 1
        raise AssertionError("被拦截的目标不应发起请求")

    def fake_settings():
        return Settings(llm_allow_private_endpoints=False)

    async def fake_runner(func, *args, **kwargs):
        result = func(*args)
        return await result if inspect.isawaitable(result) else result

    with pytest.raises(settings_service.LlmModelsUnavailableError) as excinfo:
        await settings_service.fetch_llm_models(
            1,
            LlmModelsRequest(base_url="http://169.254.169.254/v1", api_key="k"),
            settings_provider=lambda _user_id: Settings(llm_api_key="k"),
            blocking_runner=fake_runner,
            http_get=fake_http_get,
        )
    assert "出网策略" in str(excinfo.value)
    assert called["http"] == 0


class _Redirect:
    def __init__(self, location: str) -> None:
        self.status_code = 302
        self.headers = {"Location": location}
        self.is_redirect = True
        self.text = ""

    def json(self):
        raise ValueError("no body")


class _Ok:
    def __init__(self, models: list[str]) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.is_redirect = False
        self.text = "{}"
        self._models = models

    def json(self):
        return {"data": [{"id": name} for name in self._models]}


class _FakeSession:
    def __init__(self, script: list[object]) -> None:
        self.calls: list[dict] = []
        self._script = script

    def get(self, url, *, headers=None, timeout=None, allow_redirects=True):
        self.calls.append({"url": url, "allow_redirects": allow_redirects})
        return self._script.pop(0)


def _install_session(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    import app.infrastructure.http.client as http_client

    monkeypatch.setattr(http_client, "get_session", lambda: session)


async def test_models_probe_rejects_redirect_to_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """只校验第一跳是不够的：公网地址可以用 302 把服务端引到元数据地址。"""
    from app.modules.settings import service as settings_service
    from app.modules.settings.schemas import LlmModelsRequest

    session = _FakeSession([_Redirect("http://169.254.169.254/latest/meta-data/")])
    _install_session(monkeypatch, session)
    monkeypatch.setattr("app.configuration.get_settings", lambda: Settings(llm_allow_private_endpoints=False))

    async def fake_runner(func, *args, **kwargs):
        result = func(*args)
        return await result if inspect.isawaitable(result) else result

    with pytest.raises(settings_service.LlmModelsUnavailableError) as excinfo:
        await settings_service.fetch_llm_models(
            1,
            LlmModelsRequest(base_url="https://gateway.example.com/v1", api_key="k"),
            settings_provider=lambda _user_id: Settings(llm_api_key="k"),
            blocking_runner=fake_runner,
        )
    assert "出网策略" in str(excinfo.value)
    # 被拦截的跳转绝不能真的发出去
    assert [call["url"] for call in session.calls] == ["https://gateway.example.com/v1/models"]
    # 首跳必须禁止自动跟随，否则校验形同虚设
    assert session.calls[0]["allow_redirects"] is False


async def test_models_probe_follows_allowed_redirect_manually(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.settings import service as settings_service
    from app.modules.settings.schemas import LlmModelsRequest

    session = _FakeSession([_Redirect("/v1/models"), _Ok(["gpt-4o-mini"])])
    _install_session(monkeypatch, session)
    monkeypatch.setattr("app.configuration.get_settings", lambda: Settings(llm_allow_private_endpoints=False))

    async def fake_runner(func, *args, **kwargs):
        result = func(*args)
        return await result if inspect.isawaitable(result) else result

    models = await settings_service.fetch_llm_models(
        1,
        LlmModelsRequest(base_url="https://gateway.example.com/api", api_key="k"),
        settings_provider=lambda _user_id: Settings(llm_api_key="k"),
        blocking_runner=fake_runner,
    )
    assert models == ["gpt-4o-mini"]
    assert [call["url"] for call in session.calls] == [
        "https://gateway.example.com/api/models",
        # 绝对路径的 Location 相对主机解析（与 requests 行为一致）
        "https://gateway.example.com/v1/models",
    ]
