"""HK stock reference detection: auto-derived aliases and context gating."""

from app.financial_data.hk import name_reference as hk
from app.financial_data.stock.profile import name_map


def _patch_hk(monkeypatch, *, names, short, pinyin=()):
    monkeypatch.setattr(hk, "_ensure_hk_reference_indexes", lambda: None)
    monkeypatch.setattr(hk, "_hk_name_index", frozenset(names))
    monkeypatch.setattr(hk, "_hk_short_name_index", frozenset(short))
    monkeypatch.setattr(hk, "_hk_pinyin_index", frozenset(pinyin))
    monkeypatch.setattr(hk, "_hk_names", tuple(names))


def _patch_a_share(monkeypatch, *, names=(), short=(), pinyin=()):
    monkeypatch.setattr(name_map, "_stock_name_detection_index", tuple(names))
    monkeypatch.setattr(name_map, "_stock_short_name_index", frozenset(short))
    monkeypatch.setattr(name_map, "_stock_pinyin_index", frozenset(pinyin))
    monkeypatch.setattr(name_map, "_stock_reference_names", ())


def test_build_hk_name_index_excludes_ambiguous_names():
    index = hk.build_hk_name_index(["腾讯控股", "美团－Ｗ", "天安", "新世界", "长和"])

    assert index == frozenset({"腾讯控股", "美团-W"})


def test_build_hk_short_name_index_keeps_brand_two_char_names():
    index = hk.build_hk_short_name_index(
        ["腾讯控股", "美团－Ｗ", "小米集团－Ｗ", "网易", "天安"]
    )

    assert {"腾讯", "美团", "小米", "网易"} <= index
    assert "天安" not in index


def test_hk_detection_requires_context_for_short_names(monkeypatch):
    _patch_hk(monkeypatch, names=["腾讯控股"], short=["美团"], pinyin=["txkg"])

    assert hk.contains_hk_stock_name("腾讯控股财报")
    assert hk.contains_hk_stock_name("txkg 走势")
    assert not hk.contains_hk_stock_name("美团怎么样")
    assert not hk.mentions_hk_stock_target("美团")
    assert hk.mentions_hk_stock_target("美团怎么样")
    assert hk.mentions_hk_stock_target("美团新闻")


def test_aggregator_combines_a_share_and_hk(monkeypatch):
    from app.modules.chat.stock_reference import mentions_stock_target

    _patch_a_share(monkeypatch, names=["贵州茅台"], short=["茅台"])
    _patch_hk(monkeypatch, names=["腾讯控股"], short=["美团", "腾讯"])

    assert mentions_stock_target("贵州茅台发布公告")
    assert mentions_stock_target("茅台新闻")
    assert mentions_stock_target("美团怎么样")
    assert mentions_stock_target("腾讯新闻")
    assert not mentions_stock_target("友好往来新闻")


def test_capability_plan_activates_stock_analysis_for_hk_alias(monkeypatch):
    from app.modules.chat.capability_plan import build_chat_capability_plan

    _patch_a_share(monkeypatch)
    _patch_hk(monkeypatch, names=["腾讯控股"], short=["美团"])

    plan = build_chat_capability_plan("美团怎么样", max_initial_active_skills=2)

    assert "stock_analysis" in plan.initial_skill_names
