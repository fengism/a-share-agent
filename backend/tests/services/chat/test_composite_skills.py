import pytest

from app.services.chat.skills import composite_skills


async def _ok(value):
    return value


async def _fail():
    raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_gather_labeled_preserves_labels_and_errors():
    result = await composite_skills._gather_labeled({
        "a": _ok(1),
        "b": _fail(),
    })

    assert result == {"a": 1, "b": {"error": "boom"}}


@pytest.mark.asyncio
async def test_compare_stocks_keeps_per_stock_errors(monkeypatch):
    async def fake_info(code):
        if code == "000001":
            raise RuntimeError("info failed")
        return {"name": code}

    async def fake_valuation(code):
        if code == "600519":
            raise RuntimeError("valuation failed")
        return {"pe": 10}

    monkeypatch.setattr(composite_skills.helpers, "get_stock_info", fake_info)
    monkeypatch.setattr(composite_skills.helpers, "get_stock_valuation_detail", fake_valuation)

    result = await composite_skills._compare_stocks("600519,000001")

    assert result == {
        "comparison": [
            {"code": "600519", "info": {"name": "600519"}, "valuation": {"error": "valuation failed"}},
            {"code": "000001", "info": {"error": "info failed"}, "valuation": {"pe": 10}},
        ]
    }
