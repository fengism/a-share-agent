"""Short-name derivation, pinyin initials, and stock-reference detection."""

from app.financial_data.stock.profile import name_map, short_names


def _snapshot(mapping: dict[str, str]) -> name_map.StockNameMapSnapshot:
    return name_map.StockNameMapSnapshot(
        mapping=mapping,
        default_source_id="cache.legacy_stock_names",
    )


def test_build_short_name_index_derives_place_and_industry_stems():
    index = short_names.build_short_name_index(
        ["贵州茅台", "海康威视", "立讯精密", "万科Ａ", "山西汾酒"]
    )

    assert {"茅台", "海康", "立讯", "万科", "汾酒"} <= index


def test_build_short_name_index_filters_generic_words():
    index = short_names.build_short_name_index(
        ["友好集团", "人民网", "健康元", "阳光电源", "东方财富"]
    )

    assert not {"友好", "人民", "健康", "阳光", "东方"} & index


def test_build_short_name_index_keeps_exception_aliases():
    assert {"招行", "工行", "建行", "农行", "中行", "交行", "宁王"} <= (
        short_names.build_short_name_index([])
    )


def test_build_pinyin_index_derives_unique_initials():
    index = short_names.build_pinyin_index(["贵州茅台", "海康威视", "立讯精密"])

    assert {"gzmt", "hkws", "lxjm"} <= index


def test_build_pinyin_index_skips_short_forms():
    assert short_names.build_pinyin_index(["柳工"]) == frozenset()


def test_full_name_index_normalizes_full_width_suffix():
    index = name_map._build_stock_name_detection_index(_snapshot({"000002": "万科Ａ"}))

    assert "万科A" in index
    assert "万科" in index


def test_contains_known_stock_name_matches_full_name_and_pinyin(monkeypatch):
    monkeypatch.setattr(name_map, "_stock_name_detection_index", ("贵州茅台",))
    monkeypatch.setattr(name_map, "_stock_short_name_index", frozenset())
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset({"gzmt"}))

    assert name_map.contains_known_stock_name("贵州茅台发布公告")
    assert name_map.contains_known_stock_name("gzmt 走势")
    assert not name_map.contains_known_stock_name("光伏行业新闻")


def test_stock_reference_requires_context_for_derived_alias(monkeypatch):
    monkeypatch.setattr(name_map, "_stock_name_detection_index", ())
    monkeypatch.setattr(name_map, "_stock_short_name_index", frozenset({"茅台"}))
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset())

    assert not name_map.mentions_stock_target("茅台")
    assert name_map.mentions_stock_target("茅台怎么样")
    assert name_map.mentions_stock_target("茅台新闻")


def test_local_name_map_prefers_complete_file(monkeypatch):
    file_snapshot = _snapshot({"000001": "平安银行"})
    spot_calls: list[bool] = []
    monkeypatch.setattr(name_map, "_load_stock_name_file", lambda: file_snapshot)
    monkeypatch.setattr(
        name_map,
        "_load_stock_name_map_from_spot_snapshot",
        lambda: spot_calls.append(True) or None,
    )

    assert name_map._load_local_stock_name_map() is file_snapshot
    assert spot_calls == []


def test_local_name_map_falls_back_to_spot(monkeypatch):
    spot_snapshot = _snapshot({"000001": "平安银行"})
    monkeypatch.setattr(name_map, "_load_stock_name_file", lambda: None)
    monkeypatch.setattr(
        name_map,
        "_load_stock_name_map_from_spot_snapshot",
        lambda: spot_snapshot,
    )

    assert name_map._load_local_stock_name_map() is spot_snapshot


def test_classify_message_routes_alias_with_context(monkeypatch):
    monkeypatch.setattr(name_map, "_stock_name_detection_index", ())
    monkeypatch.setattr(name_map, "_stock_short_name_index", frozenset({"茅台"}))
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset())

    from app.modules.chat.routing import classify_message

    decision = classify_message(
        "茅台怎么样",
        available_agents=("technical", "fundamental", "news", "risk"),
    )

    assert decision.needs_llm_classification
    assert decision.agents == ["technical", "fundamental", "news", "risk"]


def test_build_short_name_index_keeps_frequent_long_prefixes():
    index = short_names.build_short_name_index(["三一重工", "三一重能"])

    assert "三一" in index
    assert "三一重" in index


def test_build_short_name_index_drops_rare_long_prefixes():
    index = short_names.build_short_name_index(["贵州茅台"])

    assert "贵州茅" not in index
    assert "茅台" in index
