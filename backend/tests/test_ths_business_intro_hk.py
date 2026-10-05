"""同花顺主营介绍的港股兼容：F10 路径片段与页面编码。"""

from __future__ import annotations

import pytest

from app.financial_data.stock.profile.business_intro import StockBusinessIntroService
from app.infrastructure.providers.ths.business_intro import fetch_stock_business_intro
from app.infrastructure.providers.ths.hk_f10 import ths_f10_code_segment

_HTML_TEMPLATE = (
    "<html><head><title>t</title></head><body><ul class=\"main_intro_list\">"
    "<li>主营业务：{business}</li>"
    "<li>经营范围：{scope}</li>"
    "</ul></body></html>"
)


class _FakeResponse:
    """按当前 encoding 现场解码，用来暴露编码选错的问题。"""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.encoding: str | None = None

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8", errors="replace")

    def raise_for_status(self) -> None:
        return None


class _FakeTransport:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self.urls: list[str] = []

    def request(self, method, url, *, headers=None, timeout=None, **kwargs):  # noqa: ANN001
        self.urls.append(url)
        return _FakeResponse(self._content)


# ── F10 路径片段：港股必须是 HK + 去掉前导零后补齐 4 位 ──


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("600519", "600519"),
        ("000001", "000001"),
        ("00700", "HK0700"),
        ("700", "HK0700"),
        ("hk00700", "HK0700"),
        ("09988", "HK9988"),
        ("00001", "HK0001"),
        ("00939", "HK0939"),
        ("06181", "HK6181"),
    ],
)
def test_ths_f10_code_segment(code: str, expected: str) -> None:
    assert ths_f10_code_segment(code) == expected


def test_hk_segment_is_never_five_digits() -> None:
    """同花顺港股 F10 只认 4 位写法；5 位补零只会拿到空壳页。"""
    for code in ("00700", "09988", "00939", "06181", "00001"):
        digits = ths_f10_code_segment(code)[2:]
        assert len(digits) == 4
        assert digits == digits.lstrip("0").zfill(4)


# ── 页面编码：A 股 gb2312，港股 utf-8 ──


def test_hk_page_is_decoded_as_utf8() -> None:
    business = "公司乃一间投资控股公司。集团主要提供增值服务。"
    html = _HTML_TEMPLATE.format(business=business, scope="增值服务")
    transport = _FakeTransport(html.encode("utf-8"))

    frame = fetch_stock_business_intro(transport, "00700")

    assert transport.urls == ["https://basic.10jqka.com.cn/new/HK0700/operate.html"]
    assert frame.iloc[0]["主营业务"] == business
    assert "涓昏" not in frame.iloc[0]["主营业务"]


def test_a_share_page_still_decoded_as_gb2312() -> None:
    business = "茅台酒及系列酒的生产与销售。"
    html = _HTML_TEMPLATE.format(business=business, scope="饮料、食品")
    transport = _FakeTransport(html.encode("gb2312"))

    frame = fetch_stock_business_intro(transport, "600519")

    assert transport.urls == ["https://basic.10jqka.com.cn/new/600519/operate.html"]
    assert frame.iloc[0]["主营业务"] == business
    assert frame.iloc[0]["股票代码"] == "600519"


def test_empty_intro_list_returns_empty_frame() -> None:
    transport = _FakeTransport(b"<html><body><div>no list</div></body></html>")
    assert fetch_stock_business_intro(transport, "00700").empty


# ── 服务层：港股代码归一为 5 位，与其他港股模块同一标识 ──


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("00700", "00700"),
        ("700", "00700"),
        ("hk00700", "00700"),
        ("00001", "00001"),
        ("600519", "600519"),
        ("sh600519", "600519"),
    ],
)
def test_service_normalizes_hk_code_to_five_digits(raw: str, expected: str) -> None:
    assert StockBusinessIntroService._normalize_code(raw) == expected


def test_service_rejects_non_stock_code() -> None:
    from app.core.exceptions import InvalidRequestError

    with pytest.raises(InvalidRequestError):
        StockBusinessIntroService._normalize_code("123456")
