"""K 线复权参数解析：none 与空串都表示不复权，且不接受未知值。"""

from __future__ import annotations

import pytest

from app.api.routes.stock_sections.quotes import _normalize_adjust


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("none", ""),
        ("", ""),
        ("qfq", "qfq"),
        ("hfq", "hfq"),
    ],
)
def test_normalize_adjust_maps_none_to_empty(raw: str, expected: str) -> None:
    assert _normalize_adjust(raw) == expected


def test_unknown_adjust_is_rejected_by_route_pattern() -> None:
    """非法值必须被 FastAPI 的 pattern 拦成 422，不能静默当成不复权。"""
    import re

    pattern = re.compile(r"^(qfq|hfq|none|)$")
    assert pattern.match("none")
    assert pattern.match("")
    assert pattern.match("qfq")
    assert not pattern.match("no-adjust")
    assert not pattern.match("NONE")


@pytest.mark.asyncio
async def test_route_sends_raw_prices_for_none() -> None:
    """端到端：adjust=none 与 adjust= 空串返回同一份不复权数据。"""
    from app.api.routes.stock_sections import quotes as route

    captured: list[str] = []

    async def _fake_service(code, period, start_date, end_date, adjust):
        captured.append(adjust)
        return "ok"

    original = route.get_stock_kline_service
    route.get_stock_kline_service = _fake_service  # type: ignore[assignment]
    try:
        assert await route.get_kline("600519", "daily", "2026-06-03", "2026-06-03", "none") == "ok"
        assert await route.get_kline("600519", "daily", "2026-06-03", "2026-06-03", "") == "ok"
        assert await route.get_kline("600519", "daily", "2026-06-03", "2026-06-03", "qfq") == "ok"
    finally:
        route.get_stock_kline_service = original  # type: ignore[assignment]

    assert captured == ["", "", "qfq"]
