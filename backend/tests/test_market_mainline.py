"""市场主线机会与容灾降级单元测试。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.financial_data.market.quotes import mainline as mainline_module
from app.financial_data.market.quotes.schemas import MarketMainlineResponse
from app.infrastructure.providers import cls as cls_module


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.text = json.dumps(payload, ensure_ascii=False)


_MAINLINE_PAYLOAD = {
    "errno": 0,
    "msg": "",
    "data": {
        "chance_desc": "判断主线机会",
        "chances": [
            {
                "title": "AI算力",
                "type": "continued",
                "reason": "持续活跃",
                "plates": [],
            }
        ],
        "styles": {},
    },
}


def test_fetch_market_mainline_fallback_to_secondary(monkeypatch: pytest.MonkeyPatch) -> None:
    urls_called: list[str] = []

    def mock_get(url, *, params=None, headers=None, timeout=None):  # noqa: ANN001
        urls_called.append(url)
        if "api3.cls.cn" in url:
            raise ConnectionError("Primary timed out")
        return _FakeResponse(_MAINLINE_PAYLOAD)

    monkeypatch.setattr(cls_module, "provider_get", mock_get)

    result = cls_module.ClsDataProvider().fetch_market_mainline()

    assert len(urls_called) == 2
    assert urls_called[0] == "https://api3.cls.cn/v2/dingPan/mainline"
    assert urls_called[1] == "https://www.cls.cn/v2/dingPan/mainline"
    assert len(result.get("chances", [])) == 1


@pytest.mark.asyncio
async def test_get_market_mainline_degrades_to_last_known_good(monkeypatch: pytest.MonkeyPatch) -> None:
    # 模拟上次成功的数据
    initial = MarketMainlineResponse(
        fetched_at="2026-10-21T11:40:00",
        style=None,
        items=[],
    )
    monkeypatch.setattr(mainline_module, "_last_market_mainline", initial)
    monkeypatch.setattr(mainline_module.cache, "get", lambda k: None)
    mock_set = MagicMock()
    monkeypatch.setattr(mainline_module.cache, "set", mock_set)

    mock_provider = MagicMock()
    mock_provider.fetch_market_mainline.side_effect = RuntimeError("Upstream timeout")
    monkeypatch.setattr(mainline_module, "get_provider", lambda _: mock_provider)

    res = await mainline_module.get_market_mainline()

    # 验证降级返回了历史有效数据，未抛出 503 错误
    assert res == initial
    assert mock_set.called
    assert mock_set.call_args[1].get("ttl") == 60
