"""概念板块联动：成分股聚合与相关概念筛选。"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.financial_data.market.quotes import concept_linkage as module  # noqa: E402


class _FakeCursor:
    def __init__(self, rows: list[sqlite3.Row]) -> None:
        self._rows = rows

    def fetchall(self) -> list[sqlite3.Row]:
        return self._rows


class _FakeConnection:
    """按 SQL 里的 ``json_each`` 特征区分成分股查询与概念计数查询。"""

    def __init__(self, mapping_rows: list[tuple], concept_rows: list[tuple]) -> None:
        self._mapping_rows = mapping_rows
        self._concept_rows = concept_rows

    def execute(self, sql: str, params: tuple = ()):  # noqa: ANN201
        if "json_each" in sql:
            return _FakeCursor(
                [
                    {"stock_code": code, "stock_name": name, "concepts_json": concepts}
                    for code, name, concepts in self._mapping_rows
                ]
            )
        names = set(params or ())
        return _FakeCursor(
            [{"name": name, "stock_count": count} for name, count in self._concept_rows if name in names]
        )


def _patch_connection(monkeypatch: pytest.MonkeyPatch, mapping_rows, concept_rows) -> None:
    monkeypatch.setattr(module, "_industry_connection", lambda: _FakeConnection(mapping_rows, concept_rows))


def test_list_constituents_normalizes_codes_and_parses_concepts(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connection(
        monkeypatch,
        mapping_rows=[
            ("000002.SZ", "万科A", '["住宅开发", "机器人概念"]'),
            ("600519.SH", "贵州茅台", '["白酒", "机器人概念"]'),
            ("无效代码", "坏数据", "[]"),
        ],
        concept_rows=[],
    )

    items, total = module.list_constituents("机器人概念")

    assert total == 2
    assert [item.code for item in items] == ["000002", "600519"]
    assert items[0].concepts == ["住宅开发", "机器人概念"]


def test_list_constituents_skips_unparsable_concept_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connection(
        monkeypatch,
        mapping_rows=[("000002.SZ", "万科A", "不是JSON")],
        concept_rows=[],
    )

    items, total = module.list_constituents("机器人概念")

    assert total == 1
    assert items[0].concepts == []


def test_related_concepts_excludes_overbroad_attribute_concepts(monkeypatch: pytest.MonkeyPatch) -> None:
    """融资融券这类普适属性概念对任何题材都高重叠，不应霸榜。"""
    mapping_rows = [
        (
            f"{index:06d}.SZ",
            f"股票{index}",
            '["机器人概念", "融资融券", "深股通", "人形机器人"]',
        )
        for index in range(100)
    ]
    _patch_connection(
        monkeypatch,
        mapping_rows=mapping_rows,
        concept_rows=[
            # 当前概念 100 只；融资融券 3861 只远超 2 倍上限，深股通 1879 只也在上限外
            ("融资融券", 3861),
            ("深股通", 1879),
            ("人形机器人", 40),
        ],
    )

    items, _ = module.list_constituents("机器人概念")
    related = module._related_concepts("机器人概念", items)

    assert [item.name for item in related] == ["人形机器人"]
    assert related[0].overlap == 100
    assert related[0].ratio == 1.0


def test_related_concepts_ranks_by_overlap_and_excludes_self(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connection(
        monkeypatch,
        mapping_rows=[
            ("000001.SZ", "甲", '["目标概念", "题材A", "题材B"]'),
            ("000002.SZ", "乙", '["目标概念", "题材A"]'),
            ("000003.SZ", "丙", '["目标概念", "题材B"]'),
        ],
        concept_rows=[("题材A", 2), ("题材B", 2)],
    )

    items, _ = module.list_constituents("目标概念")
    related = module._related_concepts("目标概念", items)

    # 自身不出现在结果里；题材A/B 各重叠 2 只，按重叠数排序
    assert "目标概念" not in [item.name for item in related]
    assert {item.name for item in related} == {"题材A", "题材B"}
    assert all(item.ratio == pytest.approx(2 / 3, abs=1e-4) for item in related)


def test_related_concepts_empty_when_no_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_connection(
        monkeypatch,
        mapping_rows=[("000001.SZ", "甲", '["目标概念"]')],
        concept_rows=[],
    )

    items, _ = module.list_constituents("目标概念")
    assert module._related_concepts("目标概念", items) == []


def test_get_concept_constituents_degrades_when_quotes_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """行情挂掉不应让成分股列表整体失败。"""
    _patch_connection(
        monkeypatch,
        mapping_rows=[
            ("000002.SZ", "万科A", '["机器人概念"]'),
            ("600519.SH", "贵州茅台", '["机器人概念", "白酒"]'),
        ],
        concept_rows=[("白酒", 1)],
    )

    async def _boom(codes: list[str]):
        raise RuntimeError("行情上游不可用")

    monkeypatch.setattr(module, "fetch_realtime_quote_set", _boom)
    # 行情不可用时实现会回退到"本地当日已确认收盘价"（market_daily 库）；
    # 开发机跑过归档后该兜底会命中真实数据，故显式置空以验证纯降级路径。
    _patch_local_closes(monkeypatch, {})

    result = asyncio.run(module.get_concept_constituents("机器人概念"))

    assert result["total"] == 2
    assert result["quote_covered"] == 0
    assert all(item["price"] is None for item in result["items"])
    # 成分身份仍然完整，且相关概念照常给出
    assert [item["code"] for item in result["items"]] == ["000002", "600519"]
    assert result["related_concepts"][0]["name"] == "白酒"


def test_get_concept_constituents_raises_for_unknown_concept(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.exceptions import ResourceNotFoundError

    _patch_connection(monkeypatch, mapping_rows=[], concept_rows=[])

    with pytest.raises(ResourceNotFoundError):
        asyncio.run(module.get_concept_constituents("不存在的概念"))


def _patch_local_closes(
    monkeypatch: pytest.MonkeyPatch,
    rows: dict[str, dict],
) -> list[str]:
    """桩掉本地当日收盘兜底，并记录被请求的代码。"""
    seen: list[str] = []

    def _fake(codes: list[str]) -> dict[str, dict]:
        seen.extend(codes)
        return {code: rows[code] for code in codes if code in rows}

    monkeypatch.setattr(module, "_confirmed_local_closes", _fake)
    return seen


def test_get_concept_constituents_falls_back_to_confirmed_local_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """实时行情缺失时，用本地当日已确认收盘价兜底，并标注来源。"""
    _patch_connection(
        monkeypatch,
        mapping_rows=[("000002.SZ", "万科A", '["机器人概念"]')],
        concept_rows=[],
    )

    async def _boom(codes: list[str]):
        raise RuntimeError("行情上游不可用")

    monkeypatch.setattr(module, "fetch_realtime_quote_set", _boom)
    _patch_local_closes(
        monkeypatch,
        {
            "000002": {
                "close": 4.26,
                "change_pct": 4.41,
                "amount": 5158052403,
                "source": "market_daily_close:2026-10-02",
            }
        },
    )

    result = asyncio.run(module.get_concept_constituents("机器人概念"))

    item = result["items"][0]
    assert item["price"] == 4.26
    assert item["change_pct"] == 4.41
    assert item["amount"] == 5158052403
    # 兜底数据必须能与其他来源区分开，前端据此标注"收盘价"
    assert item["quote_source"] == "market_daily_close:2026-10-02"


def test_get_concept_constituents_keeps_uncovered_codes_empty_without_local_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """本地没有当日已确认数据时，保持空值，绝不拿昨日价冒充今日价。"""
    _patch_connection(
        monkeypatch,
        mapping_rows=[("000002.SZ", "万科A", '["机器人概念"]')],
        concept_rows=[],
    )

    async def _boom(codes: list[str]):
        raise RuntimeError("行情上游不可用")

    monkeypatch.setattr(module, "fetch_realtime_quote_set", _boom)
    _patch_local_closes(monkeypatch, {})

    result = asyncio.run(module.get_concept_constituents("机器人概念"))

    assert result["items"][0]["price"] is None
    assert result["items"][0]["quote_source"] is None


def test_get_concept_constituents_prefers_realtime_over_local_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """实时行情已有的代码不再查本地兜底，两者不冲突。"""

    class _QuoteSet:
        quoted_at = "2026-10-02T15:00:00+08:00"
        source = "tdx"
        quotes = {"000002": {"price": 5.0, "change_pct": 17.4, "amount": 999}}
        quote_sources = {"000002": "tdx"}

    async def _fake_fetch(codes: list[str]):
        return _QuoteSet()

    _patch_connection(
        monkeypatch,
        mapping_rows=[("000002.SZ", "万科A", '["机器人概念"]')],
        concept_rows=[],
    )
    monkeypatch.setattr(module, "fetch_realtime_quote_set", _fake_fetch)

    requested = _patch_local_closes(
        monkeypatch,
        {"000002": {"close": 4.26, "change_pct": 4.41, "amount": 1, "source": "local"}},
    )

    result = asyncio.run(module.get_concept_constituents("机器人概念"))

    assert result["items"][0]["price"] == 5.0
    assert result["items"][0]["quote_source"] == "tdx"
    # 实时已覆盖的代码不应再去查本地
    assert requested == []


def test_confirmed_local_closes_computes_change_pct_from_previous_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """库内 change_pct 为 NULL 时，用前一个交易日 close 补算涨跌幅。"""
    _patch_connection(monkeypatch, mapping_rows=[], concept_rows=[])

    monkeypatch.setattr(
        module.market_daily_bar_service.repository,
        "list_confirmed_closes",
        lambda codes, trade_date: {
            "000002": {"close": 4.26, "pre_close": 4.08, "amount": 5158052403.74, "turnover_pct": None}
        },
    )

    result = module._confirmed_local_closes(["000002"])

    assert result["000002"]["change_pct"] == pytest.approx(4.41, abs=0.01)
    assert result["000002"]["amount"] == 5158052403
    assert result["000002"]["source"].startswith("market_daily_close:")


def test_confirmed_local_closes_skips_rows_without_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """close 缺失的脏数据不应被填成 0。"""
    _patch_connection(monkeypatch, mapping_rows=[], concept_rows=[])

    monkeypatch.setattr(
        module.market_daily_bar_service.repository,
        "list_confirmed_closes",
        lambda codes, trade_date: {"000002": {"close": None, "pre_close": 4.08, "amount": None}},
    )

    assert module._confirmed_local_closes(["000002"]) == {}


def test_get_concept_constituents_degrades_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """上游拉取行情超时应自动降级，避免阻塞整个接口。"""
    _patch_connection(
        monkeypatch,
        mapping_rows=[
            ("000002.SZ", "万科A", '["机器人概念"]'),
        ],
        concept_rows=[],
    )

    async def _slow_fetch(codes: list[str]):
        await asyncio.sleep(10)

    monkeypatch.setattr(module, "QUOTE_FETCH_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(module, "fetch_realtime_quote_set", _slow_fetch)
    # 本地当日已确认收盘兜底同样要隔离，否则跑过归档的开发机会命中真实数据。
    _patch_local_closes(monkeypatch, {})

    result = asyncio.run(module.get_concept_constituents("机器人概念", quote_codes=["000002"]))

    assert result["total"] == 1
    assert result["items"][0]["code"] == "000002"
    assert result["items"][0]["price"] is None

