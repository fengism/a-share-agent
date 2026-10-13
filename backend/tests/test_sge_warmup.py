"""上金所快照预热任务的测试。"""

from __future__ import annotations

import pytest

from app.financial_data.market.quotes import sge_gold


class _StubService:
    def __init__(self, failing: set[str] | None = None) -> None:
        self.failing = failing or set()
        self.requested: list[str] = []

    async def get(self, symbol: str):
        self.requested.append(symbol)
        if symbol in self.failing:
            raise RuntimeError(f"boom: {symbol}")
        return symbol


@pytest.fixture
def _stub_service(monkeypatch: pytest.MonkeyPatch):
    service = _StubService()
    monkeypatch.setattr(sge_gold, "_sge_gold_service", service)
    return service


@pytest.mark.asyncio
async def test_warm_up_covers_every_symbol(_stub_service: _StubService) -> None:
    stats = await sge_gold.warm_up_sge_gold_snapshots()

    assert stats == {"succeeded": len(sge_gold._SGE_SYMBOLS), "failed": 0}
    assert set(_stub_service.requested) == set(sge_gold._SGE_SYMBOLS)


@pytest.mark.asyncio
async def test_warm_up_continues_after_a_symbol_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = {"Pt99.95", "PGC30g"}
    service = _StubService(failing=failing)
    monkeypatch.setattr(sge_gold, "_sge_gold_service", service)

    stats = await sge_gold.warm_up_sge_gold_snapshots()

    assert stats["failed"] == len(failing)
    assert stats["succeeded"] == len(sge_gold._SGE_SYMBOLS) - len(failing)
    # 失败品种不能中断整体预热
    assert len(service.requested) == len(sge_gold._SGE_SYMBOLS)


@pytest.mark.asyncio
async def test_warm_up_skips_unsupported_symbols(_stub_service: _StubService) -> None:
    stats = await sge_gold.warm_up_sge_gold_snapshots(["Au99.99", "不存在的品种"])

    assert stats == {"succeeded": 1, "failed": 0}
    assert _stub_service.requested == ["Au99.99"]


@pytest.mark.asyncio
async def test_warm_up_accepts_explicit_symbol_subset(_stub_service: _StubService) -> None:
    targets = ["Au99.99", "Ag99.99"]

    stats = await sge_gold.warm_up_sge_gold_snapshots(targets)

    assert stats == {"succeeded": 2, "failed": 0}
    assert _stub_service.requested == targets


@pytest.mark.asyncio
async def test_warm_up_is_exported_from_public_module() -> None:
    from app.financial_data.market.public import warm_up_sge_gold_snapshots

    assert callable(warm_up_sge_gold_snapshots)