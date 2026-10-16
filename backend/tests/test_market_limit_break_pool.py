"""炸板池数据源：上游封装、缓存复用与失败降级。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.core.cache import market_cache
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.market.quotes import limit_break


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    market_cache.clear()


def _patch_provider(monkeypatch: pytest.MonkeyPatch, *, items: list[dict], calls: list[str]) -> None:
    def _fetch(requested_date: str) -> dict:
        calls.append(requested_date)
        return {"date": requested_date, "category": "limit_break", "items": items}

    provider = SimpleNamespace(fetch_limit_break_pool=_fetch)
    monkeypatch.setattr(limit_break, "get_provider", lambda name: provider)

    async def _call(provider_name: str, operation: str, loader, **kwargs: object) -> object:
        return await loader()

    monkeypatch.setattr(limit_break.provider_gateway, "call", _call)


async def test_limit_break_pool_normalizes_items(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _patch_provider(
        monkeypatch,
        items=[{"code": "000001", "name": "平安银行", "open_times": 3, "change_pct": 1.5}],
        calls=calls,
    )

    response = await limit_break.get_limit_break_pool(date(2026, 10, 15))

    assert calls == ["2026-10-15"]
    assert response.date == "2026-10-15"
    assert response.total == 1
    assert response.items[0].name == "平安银行"
    assert response.items[0].open_times == 3


async def test_limit_break_pool_reuses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _patch_provider(monkeypatch, items=[], calls=calls)

    await limit_break.get_limit_break_pool(date(2026, 10, 15))
    await limit_break.get_limit_break_pool(date(2026, 10, 15))

    assert calls == ["2026-10-15"]


async def test_limit_break_pool_raises_upstream_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(requested_date: str) -> dict:
        raise RuntimeError("fuyao 炸板池 500")

    monkeypatch.setattr(limit_break, "get_provider", lambda name: SimpleNamespace(fetch_limit_break_pool=_boom))

    async def _call(provider_name: str, operation: str, loader, **kwargs: object) -> object:
        return await loader()

    monkeypatch.setattr(limit_break.provider_gateway, "call", _call)

    with pytest.raises(UpstreamUnavailableError, match="炸板池上游暂时不可用"):
        await limit_break.get_limit_break_pool(date(2026, 10, 15))
