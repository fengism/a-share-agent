"""财联社 7×24 电报快讯：字段映射、签名与个股过滤。"""

from __future__ import annotations

import json

import pytest

from app.infrastructure.providers import cls as cls_module


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.text = json.dumps(payload, ensure_ascii=False)


def _patch_get(monkeypatch: pytest.MonkeyPatch, payload: dict) -> dict:
    captured: dict = {}

    def fake_get(url, *, params=None, headers=None, timeout=None):  # noqa: ANN001
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _FakeResponse(payload)

    monkeypatch.setattr(cls_module, "provider_get", fake_get)
    return captured


_ROLL_PAYLOAD = {
    "errno": 0,
    "data": {
        "roll_data": [
            {
                "id": 2505826,
                "title": "",
                "brief": "财联社10月15日电，贝莱德增持长飞光纤光缆H股。",
                "content": "财联社10月15日电，贝莱德增持长飞光纤光缆H股。",
                "ctime": 1792055090,
                "level": "C",
                "shareurl": "https://api3.cls.cn/share/article/2505826?os=web",
                "reading_num": 453965,
                "comment_num": 3,
                "author": "财联社",
                "img": "https://img.cls.cn/a.png",
            },
            {
                "id": 1,
                "title": "贵州茅台：前三季度净利润同比增长",
                "brief": "贵州茅台发布业绩预告。",
                "content": "贵州茅台发布业绩预告，预计前三季度净利润同比增长 10%。",
                "ctime": 1792055000,
                "img": "not-a-url",
            },
        ]
    },
}


def test_fetch_market_kuaixun_maps_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_get(monkeypatch, _ROLL_PAYLOAD)

    items = cls_module.ClsDataProvider().fetch_market_kuaixun()

    assert captured["url"] == "https://www.cls.cn/v1/roll/get_roll_list"
    assert captured["params"]["rn"] == "50"
    assert captured["params"]["sign"] == "59fe439c7f703f5d0c9d91e4ea15e092"
    assert len(items) == 2

    first = items[0]
    assert first.title == "财联社10月15日电，贝莱德增持长飞光纤光缆H股。"
    # brief 与 title 相同时正文留空，避免前端重复展示
    assert first.content == ""
    assert first.source == "财联社7×24快讯"
    assert first.url == "https://api3.cls.cn/share/article/2505826?os=web"
    assert first.image_url == "https://img.cls.cn/a.png"
    assert first.read_count == 453965
    assert first.comment_count == 3
    assert first.publish_time  # 已解析为可展示时间

    second = items[1]
    assert second.title == "贵州茅台：前三季度净利润同比增长"
    assert second.content == "贵州茅台发布业绩预告，预计前三季度净利润同比增长 10%。"
    # 非 http 图片地址被丢弃
    assert second.image_url == ""


def test_fetch_market_kuaixun_filters_by_stock(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_get(monkeypatch, _ROLL_PAYLOAD)

    matched = cls_module.ClsDataProvider().fetch_market_kuaixun(code="600519", code_name="贵州茅台")

    assert len(matched) == 1
    assert matched[0].title.startswith("贵州茅台")


def test_fetch_market_kuaixun_filters_ads_and_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_get(monkeypatch, {
        "errno": 0,
        "data": {
            "roll_data": [
                {"id": 1, "brief": "广告", "content": "广告", "is_ad": True},
                {"id": 2, "brief": "未入流", "content": "未入流", "in_roll": 0},
                {"id": 3, "brief": "已下线", "content": "已下线", "status": 0},
                {"id": 4, "title": "图文快讯", "brief": "图文快讯", "content": "图文快讯", "images": ["https://img.cls.cn/b.png"]},
            ]
        },
    })

    items = cls_module.ClsDataProvider().fetch_market_kuaixun()

    assert [item.title for item in items] == ["图文快讯"]
    # img 为空时回退 images 列表
    assert items[0].image_url == "https://img.cls.cn/b.png"


def test_fetch_market_kuaixun_raises_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_get(monkeypatch, {"errno": 10012, "msg": "签名错误"})

    with pytest.raises(RuntimeError, match="财联社电报接口异常"):
        cls_module.ClsDataProvider().fetch_market_kuaixun()


def test_fetch_market_kuaixun_fallback_on_primary_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    urls_called: list[str] = []

    def mock_get(url, *, params=None, headers=None, timeout=None):  # noqa: ANN001
        urls_called.append(url)
        if "www.cls.cn" in url:
            raise ConnectionError("Primary timed out")
        return _FakeResponse(_ROLL_PAYLOAD)

    monkeypatch.setattr(cls_module, "provider_get", mock_get)

    items = cls_module.ClsDataProvider().fetch_market_kuaixun()

    assert len(urls_called) == 2
    assert urls_called[0] == "https://www.cls.cn/v1/roll/get_roll_list"
    assert urls_called[1] == "https://api3.cls.cn/v1/roll/get_roll_list"
    assert len(items) == 2

