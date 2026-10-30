"""概念列表涨幅聚合：get_concept_daily_changes / list_concepts(order="change")。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.financial_data.market.quotes import concept_linkage as module  # noqa: E402


class _FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict]:
        return self._rows

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None


class _FakeMarketDailyConnection:
    """按 SQL 特征区分：交易日查询 / 两日复权价查询。"""

    def __init__(self, dates: list[str], price_rows: list[dict]) -> None:
        self._dates = dates
        self._price_rows = price_rows

    def execute(self, sql: str, params: tuple = ()):  # noqa: ANN201
        if "DISTINCT trade_date" in sql:
            return _FakeCursor([{"trade_date": date} for date in self._dates])
        if "qfq_multiplier" in sql:
            return _FakeCursor(self._price_rows)
        raise AssertionError(f"意外的 SQL: {sql}")


class _FakeIndustryConnection:
    def __init__(self, mapping_rows: list[dict], concept_rows: list[dict]) -> None:
        self._mapping_rows = mapping_rows
        self._concept_rows = concept_rows

    def execute(self, sql: str, params: tuple = ()):  # noqa: ANN201
        if "concepts_json" in sql:
            return _FakeCursor(self._mapping_rows)
        # list_concepts 用位置下标读行（sqlite3.Row 风格），返回 (name, count) 元组
        if "LIKE" in sql:
            pattern = str(params[0]) if params else ""
            keyword = pattern.strip("%")
            return _FakeCursor(
                [(row["name"], row["stock_count"]) for row in self._concept_rows if keyword in row["name"]]
            )
        ordered = sorted(self._concept_rows, key=lambda row: -row["stock_count"])
        return _FakeCursor([(row["name"], row["stock_count"]) for row in ordered])


class _FakeCache:
    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    def get(self, key: str):  # noqa: ANN201
        return self.store.get(key)

    def set(self, key: str, value: object, ttl: float) -> None:
        self.store[key] = value


def _patch(monkeypatch: pytest.MonkeyPatch, *, dates, price_rows, mapping_rows, concept_rows) -> _FakeCache:
    fake_cache = _FakeCache()
    monkeypatch.setattr(module, "cache", fake_cache)
    monkeypatch.setattr(module, "_market_daily_connection", lambda: _FakeMarketDailyConnection(dates, price_rows))
    monkeypatch.setattr(module, "_industry_connection", lambda: _FakeIndustryConnection(mapping_rows, concept_rows))
    return fake_cache


def test_get_concept_daily_changes_aggregates_equal_weight(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cache = _patch(
        monkeypatch,
        dates=["2026-09-30", "2026-09-29"],
        price_rows=[
            # 万科A：1000 → 1050，+5%
            {"code": "000002", "trade_date": "2026-09-29", "px": 1000.0},
            {"code": "000002", "trade_date": "2026-09-30", "px": 1050.0},
            # 贵州茅台：2000 → 1940，-3%
            {"code": "600519", "trade_date": "2026-09-29", "px": 2000.0},
            {"code": "600519", "trade_date": "2026-09-30", "px": 1940.0},
            # 宁德时代：+9.9%（涨停阈值内按 ≥9.8 计）
            {"code": "300750", "trade_date": "2026-09-29", "px": 200.0},
            {"code": "300750", "trade_date": "2026-09-30", "px": 219.8},
            # 只有单日价格的股票：没有前值，必须被丢弃
            {"code": "688981", "trade_date": "2026-09-30", "px": 30.0},
        ],
        mapping_rows=[
            {"stock_code": "000002.SZ", "concepts_json": '["机器人概念", "融资融券"]'},
            {"stock_code": "600519.SH", "concepts_json": '["白酒", "融资融券"]'},
            {"stock_code": "300750.SZ", "concepts_json": '["机器人概念"]'},
            {"stock_code": "688981.SH", "concepts_json": '["机器人概念"]'},
            {"stock_code": "无效代码", "concepts_json": '["机器人概念"]'},
        ],
        concept_rows=[],
    )

    changes = module.get_concept_daily_changes()

    # 机器人概念 = 万科(+5%) 与宁德(+9.9%) 等权；茅台属于白酒/融资融券，
    # 688981 无前值、无效代码被剔除
    robot = changes["机器人概念"]
    assert robot.sample_count == 2
    assert robot.change_pct == round((5.0 + 9.9) / 2, 4)
    assert robot.up_count == 2
    assert robot.down_count == 0
    assert robot.limit_up_count == 1
    assert robot.date == "2026-09-30"
    # 融资融券 = (5% - 3%) / 2，涨跌各一
    margin = changes["融资融券"]
    assert margin.sample_count == 2
    assert margin.change_pct == round((5.0 - 3.0) / 2, 4)
    assert margin.up_count == 1
    assert margin.down_count == 1
    assert changes["白酒"].change_pct == -3.0
    # 结果按日期写入缓存
    assert "concept_changes:2026-09-30" in fake_cache.store


def test_get_concept_daily_changes_returns_empty_without_two_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cache = _patch(
        monkeypatch,
        dates=["2026-09-30"],
        price_rows=[],
        mapping_rows=[{"stock_code": "000002.SZ", "concepts_json": '["机器人概念"]'}],
        concept_rows=[],
    )

    assert module.get_concept_daily_changes() == {}
    assert fake_cache.store == {}


def test_list_concepts_orders_by_change_and_merges_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cache = _patch(
        monkeypatch,
        dates=["2026-09-30", "2026-09-29"],
        price_rows=[
            {"code": "000002", "trade_date": "2026-09-29", "px": 1000.0},
            {"code": "000002", "trade_date": "2026-09-30", "px": 1050.0},
            {"code": "600519", "trade_date": "2026-09-29", "px": 2000.0},
            {"code": "600519", "trade_date": "2026-09-30", "px": 1940.0},
        ],
        mapping_rows=[
            {"stock_code": "000002.SZ", "concepts_json": '["融资融券"]'},
            {"stock_code": "600519.SH", "concepts_json": '["白酒"]'},
        ],
        concept_rows=[
            {"name": "融资融券", "stock_count": 3861},
            {"name": "白酒", "stock_count": 120},
        ],
    )

    # 默认按规模；涨跌字段无论排序方式都会附带（前端用于关联概念贴涨幅）
    by_size = module.list_concepts(limit=10)
    assert [item.name for item in by_size] == ["融资融券", "白酒"]
    assert by_size[0].change_pct == 5.0
    assert by_size[1].change_pct == -3.0

    # 按涨幅：白酒 -3% 排在融资融券 +5% 之后；字段随列表一并返回
    by_change = module.list_concepts(limit=10, order="change")
    assert [item.name for item in by_change] == ["融资融券", "白酒"]
    assert by_change[0].change_pct == 5.0
    assert by_change[0].up_count == 1
    assert by_change[0].sample_count == 1
    assert by_change[0].change_date == "2026-09-30"
    assert by_change[1].change_pct == -3.0
    assert "concept_changes:2026-09-30" in fake_cache.store


def test_list_concepts_change_order_puts_missing_data_last(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        dates=["2026-09-30", "2026-09-29"],
        price_rows=[],
        mapping_rows=[],
        concept_rows=[
            {"name": "融资融券", "stock_count": 3861},
            {"name": "白酒", "stock_count": 120},
        ],
    )

    items = module.list_concepts(limit=10, order="change")
    # 无任何聚合数据时保持规模序，字段为 None（前端按无数据渲染）
    assert [item.name for item in items] == ["融资融券", "白酒"]
    assert all(item.change_pct is None for item in items)


def test_pick_constituent_tags_prefers_specific_themes(monkeypatch: pytest.MonkeyPatch) -> None:
    sizes = {"人形机器人": 300, "预盈预增": 1800, "融资融券": 3861, "深股通": 1879, "减速器": 120, "江苏板块": 500}
    concepts = ["机器人概念", "融资融券", "预盈预增", "人形机器人", "减速器", "江苏板块", "深股通"]

    tags = module._pick_constituent_tags(
        "机器人概念",
        concepts,
        concept_size=1225,
        sizes=sizes,
    )

    # 当前概念被剔除；普适属性（融资融券/深股通，规模 > 1225×2 的已超限）不出现；
    # 最具体的三个排前面
    assert "机器人概念" not in tags
    assert tags == ["减速器", "人形机器人", "江苏板块"]


def test_pick_constituent_tags_drops_ubiquitous_tags_for_small_concepts() -> None:
    sizes = {"减速器": 120, "融资融券": 3861, "深股通": 1879}
    tags = module._pick_constituent_tags(
        "减速器",
        ["减速器", "融资融券", "深股通"],
        concept_size=120,
        sizes=sizes,
    )

    # 当前概念 120 只，2 倍上限 240：融资融券/深股通属于普适属性，必须被过滤
    assert tags == []
