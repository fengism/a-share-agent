import pytest

from app.services.chat.tools import composite_tools


async def _ok(value):
    """Return the given value unchanged as a coroutine.

    Param:
        value: the value to wrap in a coroutine.
    Return:
        the same value after awaiting.
    """
    return value


async def _fail():
    """Raise RuntimeError to simulate a failed task in gather tests.

    Return:
        never returns; always raises RuntimeError("boom").
    """
    raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_gather_labeled_preserves_labels_and_errors():
    """_gather_labeled maps coroutine results by label and captures per-task errors."""
    result = await composite_tools._gather_labeled({
        "a": _ok(1),
        "b": _fail(),
    })

    assert result == {"a": 1, "b": {"error": "boom"}}


@pytest.mark.asyncio
async def test_compare_stocks_keeps_per_stock_errors(monkeypatch):
    """_compare_stocks returns per-stock error payloads when individual helpers fail."""
    async def fake_info(code):
        if code == "000001":
            raise RuntimeError("info failed")
        return {"name": code}

    async def fake_valuation(code):
        if code == "600519":
            raise RuntimeError("valuation failed")
        return {"pe": 10}

    monkeypatch.setattr(composite_tools.helpers, "get_stock_info", fake_info)
    monkeypatch.setattr(composite_tools.helpers, "get_stock_valuation_detail", fake_valuation)

    result = await composite_tools._compare_stocks("600519,000001")

    assert result == {
        "comparison": [
            {"code": "600519", "info": {"name": "600519"}, "valuation": {"error": "valuation failed"}},
            {"code": "000001", "info": {"error": "info failed"}, "valuation": {"pe": 10}},
        ]
    }
