"""个股资料按需自动建档（ensure_basic_skeleton）的行为测试。

背景：此前个股资料缺失时不会在 stock_basic_profiles 建档，/info 不落库、
主营信息因"行不存在"写不进库。这里锁定：
- 记录不存在时创建最小档案（含板块推断 / 交易所）；
- 已存在（含手工维护）时绝不改动任何字段；
- /info 融合出的稳定字段能落库建档。
"""

from __future__ import annotations

import sqlite3

import pytest

from app.core.market import normalize_code
from app.domain.stock import StockConcept
from app.financial_data.stock.profile.basic_info import _persist_basic_profile_skeleton
from app.financial_data.stock.profile.schemas import StockBasicInfo
from app.infrastructure.persistence.connection import get_connection
from app.modules.stock_profile.repository import ensure_basic_skeleton, get_record


def _delete(code: str) -> None:
    conn = get_connection("industry")
    with conn:
        conn.execute("DELETE FROM stock_basic_profiles WHERE stock_code = ?", (code,))


def test_ensure_creates_minimal_skeleton_with_inferred_board() -> None:
    code = "699999.SH"
    _delete(code)
    try:
        created = ensure_basic_skeleton(
            stock_code=code,
            stock_name="测试股份",
            exchange="SH",
            market_group="A",
            listing_date="2020-01-01",
            source="test",
        )
        assert created is True
        record = get_record(code)
        assert record is not None
        assert record["stock_code"] == code
        assert record["stock_name"] == "测试股份"
        assert record["board"] == "主板"
        assert record["exchange"] == "SH"
        assert record["listing_date"] == "2020-01-01"
        assert record["is_manual_override"] is False
        # 未落任何波动/估值字段
        assert record["main_business"] == ""
    finally:
        _delete(code)


@pytest.mark.parametrize(
    ("code", "exchange", "expected_board"),
    [
        ("688999.SH", "SH", "科创板"),
        ("300999.SZ", "SZ", "创业板"),
        ("833999.BJ", "BJ", "北交所"),
    ],
)
def test_ensure_infers_board(code: str, exchange: str, expected_board: str) -> None:
    _delete(code)
    try:
        assert ensure_basic_skeleton(stock_code=code, exchange=exchange) is True
        assert get_record(code)["board"] == expected_board
    finally:
        _delete(code)


def test_ensure_is_idempotent_and_never_overwrites_manual() -> None:
    code = "699998.SH"
    _delete(code)
    try:
        assert ensure_basic_skeleton(stock_code=code, stock_name="首次", exchange="SH") is True
        # 第二次调用：不新增、也不改字段
        assert ensure_basic_skeleton(stock_code=code, stock_name="第二次", exchange="SH") is False
        assert get_record(code)["stock_name"] == "首次"

        # 模拟手工维护后，ensure 也不能覆盖
        conn = get_connection("industry")
        with conn:
            conn.execute(
                "UPDATE stock_basic_profiles SET is_manual_override = 1, stock_name = ? WHERE stock_code = ?",
                ("手工名", code),
            )
        assert ensure_basic_skeleton(stock_code=code, stock_name="自动名", exchange="SH") is False
        assert get_record(code)["stock_name"] == "手工名"
    finally:
        _delete(code)


def test_ensure_skips_empty_code() -> None:
    assert ensure_basic_skeleton(stock_code="   ") is False


@pytest.mark.asyncio
async def test_basic_info_persists_skeleton_for_new_code() -> None:
    raw = "688997"
    code = f"{raw}.SH"
    _delete(code)
    try:
        info = StockBasicInfo(
            code=raw,
            name="新建档案股份",
            listing_date="2015-06-01",
            exchange_industry="软件服务",
            first_industry=StockConcept(code="sw1", name="计算机"),
        )
        await _persist_basic_profile_skeleton(normalize_code(raw), info)

        record = get_record(code)
        assert record is not None
        assert record["stock_name"] == "新建档案股份"
        assert record["listing_date"] == "2015-06-01"
        assert record["industry"] == "软件服务"
        assert record["source"] == "basic_info"
    finally:
        _delete(code)


@pytest.mark.asyncio
async def test_basic_info_skips_persistence_without_identity_fields() -> None:
    raw = "688996"
    code = f"{raw}.SH"
    _delete(code)
    try:
        info = StockBasicInfo(code=raw, name="")
        await _persist_basic_profile_skeleton(normalize_code(raw), info)
        conn: sqlite3.Connection = get_connection("industry")
        assert conn.execute(
            "SELECT 1 FROM stock_basic_profiles WHERE stock_code = ?", (code,)
        ).fetchone() is None
    finally:
        _delete(code)
