"""港股自选添加：实时行情不可用或缺名称时，应退回港股证券名录补齐名称。

与 A 股使用 ``get_stock_name_map()`` 回退对齐，避免行情源波动时港股无法加入自选。
"""

from __future__ import annotations

import pytest

from app.financial_data.hk.schemas import HKStockQuotePage
from app.financial_data.hk.search_index import HKStockSearchRecord
from app.infrastructure.persistence import watchlist as watchlist_store
from app.modules.watchlist import service as watchlist_service
from app.modules.watchlist.schemas import WatchlistItemCreate


def _stored_row(storage_code: str, stock_name: str, note: str) -> dict:
    return {
        "id": 1,
        "stock_code": storage_code,
        "stock_name": stock_name,
        "note": note,
        "created_at": "2026-08-20T10:00:00",
    }


def _patch_quote_source(monkeypatch, quote_page: HKStockQuotePage) -> None:
    async def fake_get_stock_quotes(*, codes, page, page_size):  # noqa: ANN001
        return quote_page

    monkeypatch.setattr(watchlist_service.hk_market_service, "get_stock_quotes", fake_get_stock_quotes)


def _patch_directory(monkeypatch, records: list[HKStockSearchRecord]) -> None:
    async def fake_search(query: str, *, limit: int = 8):  # noqa: ANN001
        return records[:limit]

    monkeypatch.setattr(
        "app.financial_data.hk.search_index.hk_stock_search_index.search",
        fake_search,
    )


async def test_hk_add_falls_back_to_directory_name(monkeypatch) -> None:
    # 行情源返回空页（不可用），名录能查到名称
    _patch_quote_source(
        monkeypatch,
        HKStockQuotePage(items=[], total=0, page=1, page_size=1, source="sina"),
    )
    _patch_directory(monkeypatch, [HKStockSearchRecord(code="00700", name="腾讯控股")])

    captured: dict[str, str] = {}

    def fake_add_item(user_id: int, storage_code: str, stock_name: str, note: str):  # noqa: ANN001
        captured.update(user_id=str(user_id), storage_code=storage_code, stock_name=stock_name)
        return _stored_row(storage_code, stock_name, note)
    monkeypatch.setattr(watchlist_store, "add_item", fake_add_item)

    item = await watchlist_service.add_watchlist_item(
        WatchlistItemCreate(stock_code="00700", market="hk", note=""),
        user_id=7,
    )

    assert captured["stock_name"] == "腾讯控股"
    assert captured["storage_code"] == "HK:00700"
    assert item.stock_name == "腾讯控股"
    assert item.market == "hk"


async def test_hk_add_raises_when_quote_and_directory_both_miss(monkeypatch) -> None:
    _patch_quote_source(
        monkeypatch,
        HKStockQuotePage(items=[], total=0, page=1, page_size=1, source="sina"),
    )
    _patch_directory(monkeypatch, [])

    with pytest.raises(watchlist_service.UnknownWatchlistStockError):
        await watchlist_service.add_watchlist_item(
            WatchlistItemCreate(stock_code="00700", market="hk", note=""),
            user_id=7,
        )
