"""Short-name derivation, pinyin initials, and stock-reference detection."""

from app.financial_data.stock.profile import name_map, short_names
from app.financial_data.stock.profile.short_names import build_first_char_index


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
    # 索引与文件签名要一起锁定：否则真实 data/stock_names.json 会让索引被重建。
    monkeypatch.setattr(name_map, "_stock_name_file_signature", lambda: None)
    monkeypatch.setattr(name_map, "_stock_source_key", None)
    monkeypatch.setattr(name_map, "_stock_name_detection_index", build_first_char_index(("贵州茅台",)))
    monkeypatch.setattr(name_map, "_stock_short_name_index", build_first_char_index(frozenset()))
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset({"gzmt"}))

    assert name_map.contains_known_stock_name("贵州茅台发布公告")
    assert name_map.contains_known_stock_name("gzmt 走势")
    assert not name_map.contains_known_stock_name("光伏行业新闻")


def test_stock_reference_requires_context_for_derived_alias(monkeypatch):
    monkeypatch.setattr(name_map, "_stock_name_file_signature", lambda: None)
    monkeypatch.setattr(name_map, "_stock_source_key", None)
    monkeypatch.setattr(name_map, "_stock_name_detection_index", build_first_char_index(()))
    monkeypatch.setattr(name_map, "_stock_short_name_index", build_first_char_index(frozenset({"茅台"})))
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
    monkeypatch.setattr(name_map, "_stock_name_file_signature", lambda: None)
    monkeypatch.setattr(name_map, "_stock_source_key", None)
    monkeypatch.setattr(name_map, "_stock_name_detection_index", build_first_char_index(()))
    monkeypatch.setattr(name_map, "_stock_short_name_index", build_first_char_index(frozenset({"茅台"})))
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


# --- 名称文件更新后自动重建索引（新股上市）----------------------------------


def _write_name_file(path, mapping: dict[str, str]) -> None:
    import json

    path.write_text(
        json.dumps(
            {"source_id": "test", "source_overrides": {}, "mapping": mapping},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _use_temp_name_file(monkeypatch, tmp_path, mapping: dict[str, str]):
    from app.financial_data.stock.profile import name_map as module

    name_file = tmp_path / "stock_names.json"
    _write_name_file(name_file, mapping)
    monkeypatch.setattr(module, "_STOCK_NAME_FILE", name_file)
    monkeypatch.setattr(module, "_stock_source_key", None)
    monkeypatch.setattr(module, "_stock_name_detection_index", None)
    monkeypatch.setattr(module, "_stock_reference_names", ())
    monkeypatch.setattr(module, "_stock_short_name_index", None)
    monkeypatch.setattr(module, "_stock_pinyin_index", None)
    monkeypatch.setattr(module, "_load_stock_name_map_from_spot_snapshot", lambda: None)
    return name_file


def test_new_stock_name_is_recognized_after_the_file_changes(monkeypatch, tmp_path):
    """长跑进程里新上市股票的名称必须能被认出来，不能等重启。"""
    base = {f"{600000 + index:06d}": f"测试股{index}号" for index in range(4200)}
    base["600519"] = "贵州茅台"
    name_file = _use_temp_name_file(monkeypatch, tmp_path, base)

    assert name_map.contains_known_stock_name("分析贵州茅台")
    assert not name_map.contains_known_stock_name("分析乙新股科技")

    # 上游新增一只股票后文件被重写
    _write_name_file(name_file, {**base, "301999": "乙新股科技"})

    assert name_map.contains_known_stock_name("分析乙新股科技")
    # 派生简称索引也要跟着更新
    assert name_map.contains_short_stock_name("乙新股")


def test_unchanged_file_does_not_rebuild_the_index(monkeypatch, tmp_path):
    base = {f"{600000 + index:06d}": f"测试股{index}号" for index in range(4200)}
    _use_temp_name_file(monkeypatch, tmp_path, base)

    builds: list[int] = []
    original = name_map._build_stock_name_detection_index

    def _counting(snapshot):
        builds.append(len(snapshot.mapping))
        return original(snapshot)

    monkeypatch.setattr(name_map, "_build_stock_name_detection_index", _counting)

    name_map._ensure_stock_name_index()
    name_map._ensure_stock_name_index()
    name_map.contains_known_stock_name("测试股1号")

    assert len(builds) == 1, "文件没变时不该重复构建索引"


def test_derived_indexes_are_invalidated_with_the_file(monkeypatch, tmp_path):
    base = {f"{600000 + index:06d}": f"测试股{index}号" for index in range(4200)}
    name_file = _use_temp_name_file(monkeypatch, tmp_path, base)

    name_map._ensure_short_name_index()
    assert name_map._stock_short_name_index is not None

    _write_name_file(name_file, {**base, "301999": "乙新股科技"})
    name_map._ensure_stock_name_index()

    assert name_map._stock_short_name_index is None, "文件变化后简称索引必须失效"
    assert name_map._stock_pinyin_index is None, "文件变化后拼音索引必须失效"


def test_missing_name_file_degrades_without_crashing(monkeypatch, tmp_path):
    from app.financial_data.stock.profile import name_map as module

    monkeypatch.setattr(module, "_STOCK_NAME_FILE", tmp_path / "absent.json")
    # 名称文件缺失时实现会回退到本地全市场快照（backend/data/stock_spot_snapshot.json）；
    # 那是真实部署里存在的文件，开发机跑过应用后就会让本用例失去意义，因此显式隔离。
    monkeypatch.setattr(module, "_load_stock_name_map_from_spot_snapshot", lambda: None)
    monkeypatch.setattr(module, "_stock_source_key", None)
    monkeypatch.setattr(module, "_stock_name_detection_index", None)
    monkeypatch.setattr(module, "_stock_reference_names", None)
    monkeypatch.setattr(module, "_stock_short_name_index", None)
    monkeypatch.setattr(module, "_stock_pinyin_index", None)
    monkeypatch.setattr(module, "_STOCK_NAME_MAP_SERVICE", type(
        "S", (), {"get_cached": staticmethod(lambda: None)},
    )())

    assert module.contains_known_stock_name("分析贵州茅台") is False
    assert len(module._stock_name_detection_index or ()) == 0


# --- 首字符预筛索引（性能优化，语义必须与全量扫描一致）---------------------


def test_first_char_index_matches_full_scan_oracle():
    """预筛只跳过「首字符都不在文本里」的名称，结论必须与全量扫描逐条一致。"""
    names = [
        "贵州茅台", "宁德时代", "中芯国际", "万科A", "光伏科技", "中国平安",
        "平安银行", "比亚迪", "东方财富", "药明康德",
    ]
    index = short_names.build_first_char_index(names)
    messages = [
        "分析贵州茅台",
        "宁德时代和中芯国际哪个好",
        "今天大盘怎么样",
        "光伏行业新闻",
        "万科A 走势",
        "完全没有提到任何股票",
        "",
        "茅",           # 单字不足以构成名称
        "台茅台",       # 名称不是前缀也能命中
    ]
    for message in messages:
        expected = any(name in message for name in names)
        assert index.matches(message) is expected, message


def test_first_char_index_is_sound_for_every_name():
    """每个名称用自己的名字作为文本时必须命中（首字符分桶不能漏）。"""
    names = ["贵州茅台", "宁德时代", "万科A", "中芯国际"]
    index = short_names.build_first_char_index(names)
    for name in names:
        assert index.matches(f"请分析{name}的估值"), name
        assert name in index


def test_first_char_index_handles_empty_inputs():
    empty = short_names.build_first_char_index(())
    assert len(empty) == 0
    assert not empty.matches("任意文本")
    assert not empty

    index = short_names.build_first_char_index(["贵州茅台"])
    assert not index.matches("")


def test_detection_index_uses_first_char_buckets():
    """生产路径必须走预筛索引，而不是退回全量扫描。"""
    index = name_map._build_stock_name_detection_index(
        _snapshot({"600519": "贵州茅台", "300750": "宁德时代"})
    )

    assert isinstance(index, short_names.FirstCharIndex)
    assert index.matches("分析贵州茅台")
    assert not index.matches("分析光伏行业")
