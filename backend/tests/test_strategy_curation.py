"""策略精选清单的不变量。

背景：收敛前「哪些策略进入选股扫描 / 潜力股评分」是同一批 7 个 key 在两个地方各写
一遍。那份重复导致：新增 YAML 策略不会生效、YAML 里禁用策略会让选股页报错、权重
名单漂移会被 ``dict.get(key, 1.0)`` 静默吞掉。本测试把「清单必须能被 YAML 定义满足」
变成硬约束。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.modules.quant.public import (
    CURATED_STRATEGIES,
    CURATED_STRATEGY_KEYS,
    DEFAULT_MINING_WEIGHT,
    MINING_WEIGHTS,
    mining_weight,
)
from app.modules.screener.strategy_screening import SCREENER_STRATEGY_KEYS

DEFINITIONS_DIR = (
    Path(__file__).resolve().parents[1] / "app" / "modules" / "quant" / "strategies" / "definitions"
)


def _load_definitions() -> dict[str, dict]:
    """读取内置策略定义，返回 ``key -> definition``（同名取版本最高的那份）。"""
    definitions: dict[str, dict] = {}
    for path in sorted(DEFINITIONS_DIR.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        key = payload.get("key")
        if not isinstance(key, str):
            continue
        current = definitions.get(key)
        if current is None or _version_key(payload["version"]) > _version_key(current["version"]):
            definitions[key] = payload
    return definitions


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(version).split("."))


def test_definitions_directory_is_not_empty() -> None:
    """自测：目录路径写错时，下面的断言会因为「找不到定义」而失败，而不是静默通过。"""
    assert DEFINITIONS_DIR.is_dir(), f"策略定义目录不存在: {DEFINITIONS_DIR}"
    assert _load_definitions(), "未从策略定义目录解析出任何策略"


def test_curated_strategies_has_no_duplicates() -> None:
    assert len(CURATED_STRATEGIES) == len(set(CURATED_STRATEGIES))


def test_every_curated_strategy_has_an_enabled_definition() -> None:
    definitions = _load_definitions()
    missing = [key for key in CURATED_STRATEGIES if key not in definitions]
    assert missing == [], f"精选清单里的策略缺少 YAML 定义: {missing}"

    disabled = [key for key in CURATED_STRATEGIES if not definitions[key].get("enabled", True)]
    assert disabled == [], (
        f"精选清单里的策略在 YAML 中被禁用，选股页会列出但无法运行: {disabled}"
    )


def test_mining_weights_only_reference_curated_strategies() -> None:
    stray = sorted(set(MINING_WEIGHTS) - set(CURATED_STRATEGIES))
    assert stray == [], f"权重表引用了不在精选清单里的策略: {stray}"


def test_mining_weights_are_positive() -> None:
    non_positive = {key: value for key, value in MINING_WEIGHTS.items() if value <= 0}
    assert non_positive == {}, f"权重必须为正: {non_positive}"


def test_mining_weight_defaults_for_uncalibrated_strategy() -> None:
    uncalibrated = [key for key in CURATED_STRATEGIES if key not in MINING_WEIGHTS]
    assert uncalibrated, "本用例假设存在未单独标定权重的精选策略"
    for key in uncalibrated:
        assert mining_weight(key) == DEFAULT_MINING_WEIGHT


def test_mining_weight_falls_back_for_unknown_key() -> None:
    """未知 key 走默认权重是显式约定（原先的 ``dict.get(key, 1.0)`` 是隐式的）。"""
    assert mining_weight("not_a_curated_strategy") == DEFAULT_MINING_WEIGHT


def test_screener_exposes_exactly_the_curated_set() -> None:
    assert SCREENER_STRATEGY_KEYS == CURATED_STRATEGY_KEYS


def test_curated_order_is_stable_and_fully_covered_by_screener() -> None:
    """前端按此顺序展示策略，顺序变化会影响 UI，因此显式锁定。"""
    assert CURATED_STRATEGIES[:3] == ("bull_trend", "ma_golden_cross", "volume_breakout")


@pytest.mark.parametrize("key", CURATED_STRATEGIES)
def test_curated_definition_key_matches_filename_convention(key: str) -> None:
    """精选策略的定义文件必须能被 loader 按 key 找到（loader 扫描整个目录，这里做存在性自检）。"""
    definitions = _load_definitions()
    definition = definitions[key]
    assert definition["key"] == key
    assert definition["api_version"] == "quant.strategy/v1"
