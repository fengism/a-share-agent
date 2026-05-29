import json

import pandas as pd
import pytest

from app.services.screener import industry


def clear_industry_cache() -> None:
    industry.cache.delete(industry._INDUSTRY_MAPPING_CACHE_KEY)
    industry.cache.delete(industry._INDUSTRY_LIST_CACHE_KEY)
    mapping_key, list_key = industry._built_cache_keys()
    industry.cache.delete(mapping_key)
    industry.cache.delete(list_key)


def test_normalize_sw_industry_name_strips_suffix_and_empty_values():
    assert industry._normalize_sw_industry_name("半导体(申万)") == "半导体"
    assert industry._normalize_sw_industry_name(" 白酒 ") == "白酒"
    assert industry._normalize_sw_industry_name("") is None
    assert industry._normalize_sw_industry_name("nan") is None
    assert industry._normalize_sw_industry_name(None) is None


def test_build_mapping_skips_empty_sw_components(monkeypatch):
    monkeypatch.setattr(
        industry._akshare_provider,
        "fetch_sw_index_realtime",
        lambda: pd.DataFrame([{"指数代码": "801120", "指数名称": "半导体(申万)"}]),
    )
    monkeypatch.setattr(industry._akshare_provider, "fetch_sw_index_components", lambda symbol: pd.DataFrame())

    mapping, industry_list = industry._build_industry_mapping_sw_second_index_akshare()

    assert mapping == {}
    assert industry_list == ["半导体"]



def test_build_mapping_falls_back_to_east_direct_when_sw_invalid(monkeypatch):
    clear_industry_cache()
    mapping = {"600519": "白酒", "000858": "白酒"}

    monkeypatch.setattr(industry, "_MIN_VALID_MAPPING_SIZE", 1)
    monkeypatch.setattr(industry, "_build_industry_mapping_sw_second_index_akshare", lambda: ({}, []))
    monkeypatch.setattr(industry._eastmoney_provider, "build_industry_mapping_direct", lambda: (mapping, ["白酒"]))

    result_mapping, result_industry_list = industry._build_industry_mapping_sw_second()

    assert result_mapping == mapping
    assert result_industry_list == ["白酒"]


def test_fetch_industry_mapping_uses_memory_cache(monkeypatch, tmp_path):
    clear_industry_cache()
    mapping_file = tmp_path / "industry_second_mapping.json"
    mapping_file.write_text(json.dumps({"600519": "白酒"}), encoding="utf-8")

    monkeypatch.setattr(industry, "_INDUSTRY_MAPPING_FILE", mapping_file)

    mapping, industry_list = industry.fetch_industry_mapping_sw_second()
    mapping_file.write_text(json.dumps({"000858": "白酒"}), encoding="utf-8")
    cached_mapping, cached_industry_list = industry.fetch_industry_mapping_sw_second()

    assert mapping == {"600519": "白酒"}
    assert industry_list == ["白酒"]
    assert cached_mapping == mapping
    assert cached_industry_list == industry_list


def test_fetch_industry_mapping_rebuilds_when_file_missing(monkeypatch, tmp_path):
    clear_industry_cache()
    mapping = {"600519": "白酒"}

    monkeypatch.setattr(industry, "_INDUSTRY_MAPPING_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(industry, "update_industry_mapping_sw_second_file", lambda: (mapping, ["白酒"]))

    result_mapping, result_industry_list = industry.fetch_industry_mapping_sw_second()

    assert result_mapping == mapping
    assert result_industry_list == ["白酒"]


def test_fetch_industry_mapping_rebuilds_when_file_format_invalid(monkeypatch, tmp_path):
    clear_industry_cache()
    mapping_file = tmp_path / "industry_second_mapping.json"
    mapping_file.write_text(json.dumps(["invalid"]), encoding="utf-8")
    mapping = {"600519": "白酒"}

    monkeypatch.setattr(industry, "_INDUSTRY_MAPPING_FILE", mapping_file)
    monkeypatch.setattr(industry, "update_industry_mapping_sw_second_file", lambda: (mapping, ["白酒"]))

    result_mapping, result_industry_list = industry.fetch_industry_mapping_sw_second()

    assert result_mapping == mapping
    assert result_industry_list == ["白酒"]


def test_update_industry_mapping_refreshes_memory_cache(monkeypatch, tmp_path):
    clear_industry_cache()
    mapping_file = tmp_path / "industry_second_mapping.json"
    mapping = {f"60{i:04d}": "白酒" for i in range(4001)}

    monkeypatch.setattr(industry, "_INDUSTRY_MAPPING_FILE", mapping_file)
    monkeypatch.setattr(industry, "_build_industry_mapping_sw_second", lambda: (mapping, ["白酒"]))
    industry.cache.set(industry._INDUSTRY_MAPPING_CACHE_KEY, {"000001": "旧行业"}, ttl=86400)
    industry.cache.set(industry._INDUSTRY_LIST_CACHE_KEY, ["旧行业"], ttl=86400)

    updated_mapping, updated_industry_list = industry.update_industry_mapping_sw_second_file()
    cached_mapping, cached_industry_list = industry.fetch_industry_mapping_sw_second()

    assert updated_mapping == mapping
    assert updated_industry_list == ["白酒"]
    assert cached_mapping == mapping
    assert cached_industry_list == ["白酒"]
    assert json.loads(mapping_file.read_text(encoding="utf-8")) == mapping


def test_update_industry_mapping_does_not_write_invalid_mapping(monkeypatch, tmp_path):
    clear_industry_cache()
    mapping_file = tmp_path / "industry_second_mapping.json"

    monkeypatch.setattr(industry, "_INDUSTRY_MAPPING_FILE", mapping_file)
    monkeypatch.setattr(industry, "_build_industry_mapping_sw_second", lambda: ({"600519": "白酒"}, ["白酒"]))

    mapping, industry_list = industry.update_industry_mapping_sw_second_file()

    assert mapping == {"600519": "白酒"}
    assert industry_list == ["白酒"]
    assert not mapping_file.exists()


@pytest.mark.asyncio
async def test_async_accessors_return_expected_parts(monkeypatch):
    mapping = {"600519": "白酒"}

    monkeypatch.setattr(industry, "fetch_industry_mapping_sw_second", lambda: (mapping, ["白酒"]))

    assert await industry.build_industry_mapping() == (mapping, ["白酒"])
    assert await industry.get_industry_mapping() == mapping
    assert await industry.get_industry_list() == ["白酒"]
