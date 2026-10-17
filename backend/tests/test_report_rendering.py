"""报表渲染共享设施（app.infrastructure.report / app.core.urls）契约。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.urls import safe_http_url
from app.infrastructure.report import browser as report_browser


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.com/a?b=1", "https://example.com/a?b=1"),
        ("  http://example.com  ", "http://example.com"),
        ("HTTPS://Example.com/X", "HTTPS://Example.com/X"),
        ("", ""),
        (None, ""),
        ("   ", ""),
        # 非 http(s) 协议与外链注入向量
        ("javascript:alert(1)", ""),
        ("data:text/html,<script>", ""),
        ("file:///etc/passwd", ""),
        ("ftp://example.com/x", ""),
        # 缺少主机
        ("http:///path-only", ""),
        ("/relative/path", ""),
        ("#fragment", ""),
        # 非字符串输入不应抛错（原先的实现会 AttributeError）
        (123, ""),
        ({"url": "https://example.com"}, ""),
    ],
)
def test_safe_http_url(value: object, expected: str) -> None:
    assert safe_http_url(value) == expected


class _FakeElement:
    def __init__(self, name: str) -> None:
        self.name = name

    def screenshot(self) -> bytes:
        return f"png:{self.name}".encode()


class _FakePage:
    def __init__(self, selector_map: dict[str, _FakeElement | None]) -> None:
        self.selector_map = selector_map
        self.set_content_calls: list[tuple[str, str]] = []
        self.waited: list[tuple[str, int]] = []
        self.screenshot_error: Exception | None = None

    def set_content(self, html: str, *, wait_until: str) -> None:
        self.set_content_calls.append((html, wait_until))

    def wait_for_selector(self, selector: str, *, timeout: int) -> None:
        self.waited.append((selector, timeout))

    def query_selector(self, selector: str) -> _FakeElement | None:
        element = self.selector_map.get(selector)
        if element is not None and self.screenshot_error is not None:
            raise self.screenshot_error
        return element


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self.page = page
        self.launch_options: dict[str, Any] = {}
        self.viewport_options: dict[str, Any] = {}
        self.closed = False
        self.close_error: Exception | None = None

    def new_page(self, **kwargs: Any) -> _FakePage:
        self.viewport_options = kwargs
        return self.page

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _FakePlaywright:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.chromium = self

    def launch(self, **kwargs: Any) -> _FakeBrowser:
        self._browser.launch_options = kwargs
        return self._browser


class _FakeSyncPlaywrightContext:
    def __init__(self, browser: _FakeBrowser) -> None:
        self._playwright = _FakePlaywright(browser)
        self._playwright._browser = browser

    def __enter__(self) -> _FakePlaywright:
        return self._playwright

    def __exit__(self, *exc_info: object) -> bool:
        return False


def _install_fake_playwright(monkeypatch: pytest.MonkeyPatch, page: _FakePage) -> _FakeBrowser:
    browser = _FakeBrowser(page)
    monkeypatch.setattr(
        report_browser,
        "sync_playwright",
        lambda: _FakeSyncPlaywrightContext(browser),
    )
    return browser


def test_render_elements_returns_empty_without_launching_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail() -> None:
        raise AssertionError("空任务列表不应启动浏览器")

    monkeypatch.setattr(report_browser, "sync_playwright", _fail)

    assert report_browser.render_elements_to_pngs([], viewport_width=100, viewport_height=100) == []


def test_render_elements_skips_empty_selectors_without_launching(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail() -> None:
        raise AssertionError("选择器全为空时不应启动浏览器")

    monkeypatch.setattr(report_browser, "sync_playwright", _fail)

    jobs = [("无选择器", "<html></html>", "")]
    assert report_browser.render_elements_to_pngs(jobs, viewport_width=100, viewport_height=100) == []


def test_render_elements_captures_each_matching_element(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage({".card": _FakeElement("card")})
    browser = _install_fake_playwright(monkeypatch, page)

    images = report_browser.render_elements_to_pngs(
        [("标题A", "<html>A</html>", ".card"), ("标题B", "<html>B</html>", ".card")],
        viewport_width=320,
        viewport_height=240,
    )

    assert images == [("标题A", b"png:card"), ("标题B", b"png:card")]
    assert page.set_content_calls == [("<html>A</html>", "networkidle"), ("<html>B</html>", "networkidle")]
    assert browser.viewport_options == {"viewport": {"width": 320, "height": 240}, "device_scale_factor": 2}
    assert browser.closed is True


def test_render_elements_skips_missing_element_and_keeps_going(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage({".present": _FakeElement("ok")})
    _install_fake_playwright(monkeypatch, page)

    images = report_browser.render_elements_to_pngs(
        [("缺失", "<html>1</html>", ".absent"), ("命中", "<html>2</html>", ".present")],
        viewport_width=10,
        viewport_height=10,
    )

    assert images == [("命中", b"png:ok")]


def test_render_elements_waits_for_ready_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage({".panel": _FakeElement("panel")})
    _install_fake_playwright(monkeypatch, page)

    report_browser.render_elements_to_pngs(
        [("图表", "<html></html>", ".panel")],
        viewport_width=10,
        viewport_height=10,
        wait_until="load",
        ready_selector="#chart canvas",
        ready_timeout_ms=1234,
    )

    assert page.set_content_calls == [("<html></html>", "load")]
    assert page.waited == [("#chart canvas", 1234)]


def test_render_elements_closes_browser_on_screenshot_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage({".card": _FakeElement("card")})
    page.screenshot_error = RuntimeError("截图失败")
    browser = _install_fake_playwright(monkeypatch, page)

    with pytest.raises(RuntimeError, match="截图失败"):
        report_browser.render_elements_to_pngs(
            [("标题", "<html></html>", ".card")],
            viewport_width=10,
            viewport_height=10,
        )

    assert browser.closed is True


def test_render_elements_passes_sandbox_args_and_scale_override(monkeypatch: pytest.MonkeyPatch) -> None:
    page = _FakePage({".card": _FakeElement("card")})
    browser = _install_fake_playwright(monkeypatch, page)

    report_browser.render_elements_to_pngs(
        [("标题", "<html></html>", ".card")],
        viewport_width=10,
        viewport_height=10,
        device_scale_factor=1,
    )

    assert browser.launch_options["channel"] == "chromium"
    assert "--no-sandbox" in browser.launch_options["args"]
    assert "--disable-dev-shm-usage" in browser.launch_options["args"]
    assert browser.viewport_options["device_scale_factor"] == 1
